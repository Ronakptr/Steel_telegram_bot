import asyncio
import hashlib
import io
import re
from dataclasses import dataclass
from typing import Any, Iterable

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError

from config import (
    OCR_LANG,
    OCR_TIMEOUT_SECONDS,
    RECEIPT_ACCOUNT_HOLDER,
    RECEIPT_CARD_LAST4,
    TESSERACT_CMD,
)

Image.MAX_IMAGE_PIXELS = 25_000_000

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_AMOUNT_WORDS = ("مبلغ", "واریز", "انتقال", "پرداخت", "برداشت", "تراکنش")
_RECEIPT_WORDS = (
    "رسید", "واریز", "انتقال", "پرداخت", "تراکنش", "شماره پیگیری",
    "کارت مقصد", "حساب مقصد", "موفق", "بانک", "مبدا", "مقصد",
)
_TRACKING_WORDS = ("پیگیری", "مرجع", "رهگیری", "شناسه تراکنش", "شماره تراکنش")
_DATE_WORDS = ("تاریخ", "زمان", "ساعت")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_digits(text: str) -> str:
    return (text or "").translate(_PERSIAN_DIGITS)


def _clean_line(line: str) -> str:
    line = normalize_digits(line)
    line = line.replace("٬", ",").replace("،", ",")
    return re.sub(r"\s+", " ", line).strip()


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", normalize_digits(value or ""))


def _number_candidates(line: str) -> list[int]:
    normalized = _clean_line(line)
    raw = re.findall(r"(?<!\d)(?:\d[\d,\.\s]{2,}\d|\d{3,})(?!\d)", normalized)
    values: list[int] = []
    for token in raw:
        digits = re.sub(r"\D", "", token)
        if not digits or len(digits) > 15:
            continue
        try:
            values.append(int(digits))
        except ValueError:
            continue
    return values


def _is_card_like(number: int) -> bool:
    return len(str(abs(number))) in (16, 19)


def _is_tracking_like(number: int) -> bool:
    return 6 <= len(str(abs(number))) <= 14


def _amount_from_text(text: str, expected_amount: int) -> tuple[int | None, bool | None]:
    lines = [_clean_line(line) for line in (text or "").splitlines() if _clean_line(line)]
    scored: list[tuple[int, int]] = []

    for line in lines:
        lower = line.lower()
        has_amount_word = any(word in lower for word in _AMOUNT_WORDS)
        has_unit = "تومان" in lower or "ریال" in lower or "rial" in lower or "toman" in lower
        has_tracking_word = any(word in lower for word in _TRACKING_WORDS)

        for value in _number_candidates(line):
            if value <= 0 or _is_card_like(value):
                continue

            converted = value
            if "ریال" in lower or "rial" in lower:
                converted = value // 10

            score = 0
            if has_amount_word:
                score += 6
            if has_unit:
                score += 5
            if has_tracking_word:
                score -= 7
            if len(str(value)) < 4:
                score -= 5

            if expected_amount > 0:
                if converted == expected_amount:
                    score += 12
                elif value == expected_amount * 10:
                    converted = expected_amount
                    score += 10
                else:
                    distance = abs(converted - expected_amount) / max(expected_amount, 1)
                    if distance <= 0.01:
                        score += 8
                    elif distance <= 0.1:
                        score += 3

            scored.append((score, converted))

    if not scored:
        return None, None

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best_score, best_value = scored[0]
    if best_score < 3:
        return None, None
    return best_value, (best_value == expected_amount if expected_amount > 0 else None)


def _tracking_from_text(text: str) -> str | None:
    lines = [_clean_line(line) for line in (text or "").splitlines() if _clean_line(line)]
    for line in lines:
        if not any(word in line for word in _TRACKING_WORDS):
            continue
        candidates = _number_candidates(line)
        candidates = [n for n in candidates if _is_tracking_like(n) and not _is_card_like(n)]
        if candidates:
            return str(max(candidates, key=lambda n: len(str(n))))
    return None


def _date_from_text(text: str) -> str | None:
    normalized = normalize_digits(text or "")
    patterns = (
        r"\b(?:13|14|20)\d{2}[/-](?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])\b",
        r"\b(?:0?[1-9]|[12]\d|3[01])[/-](?:0?[1-9]|1[0-2])[/-](?:13|14|20)\d{2}\b",
        r"\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\b",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return match.group(0)
    return None


def _destination_last4_from_text(text: str) -> str | None:
    normalized = normalize_digits(text or "")
    expected = _digits_only(RECEIPT_CARD_LAST4)[-4:]

    for line in normalized.splitlines():
        is_destination_line = any(word in line for word in ("مقصد", "کارت", "حساب"))
        tokens = re.findall(r"(?:\d[\d*Xx-]{3,}\d|\d{4,})", line.replace(" ", ""))
        for token in tokens:
            digits = _digits_only(token)
            looks_like_card = len(digits) >= 12 or "*" in token or "X" in token or "x" in token
            if len(digits) < 4 or not (is_destination_line or looks_like_card):
                continue
            last4 = digits[-4:]
            if expected and last4 == expected:
                return expected
            if is_destination_line:
                return last4
    return None


def _destination_name_matches(text: str) -> bool | None:
    expected = (RECEIPT_ACCOUNT_HOLDER or "").strip()
    if not expected:
        return None
    normalized_text = re.sub(r"\s+", "", text or "")
    normalized_expected = re.sub(r"\s+", "", expected)
    if not normalized_text:
        return None
    return normalized_expected in normalized_text


def _receipt_keyword_score(text: str) -> int:
    normalized = text or ""
    return sum(1 for word in _RECEIPT_WORDS if word in normalized)


def _prepare_images(image_bytes: bytes) -> list[Image.Image]:
    try:
        with Image.open(io.BytesIO(image_bytes)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("فایل ارسالی تصویر معتبر نیست.") from exc

    max_side = 3200
    if max(image.size) > max_side:
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    elif min(image.size) < 900:
        scale = min(2.0, 900 / max(min(image.size), 1))
        image = image.resize(
            (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
            Image.Resampling.LANCZOS,
        )

    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    gray = ImageEnhance.Contrast(gray).enhance(1.35)
    sharp = gray.filter(ImageFilter.SHARPEN)
    threshold = sharp.point(lambda p: 255 if p > 165 else 0)
    return [sharp, threshold]


def _ocr_sync(image_bytes: bytes) -> str:
    images = _prepare_images(image_bytes)
    outputs: list[str] = []
    configs = ("--oem 1 --psm 6", "--oem 1 --psm 11")

    for image, config in zip(images, configs):
        text = pytesseract.image_to_string(
            image,
            lang=OCR_LANG,
            config=config,
            timeout=OCR_TIMEOUT_SECONDS,
        )
        if text.strip():
            outputs.append(text.strip())
    return "\n".join(outputs)


def analyze_ocr_text(text: str, expected_amount: int) -> dict[str, Any]:
    cleaned_text = "\n".join(_clean_line(line) for line in (text or "").splitlines() if _clean_line(line))
    amount, amount_matches = _amount_from_text(cleaned_text, expected_amount)
    tracking = _tracking_from_text(cleaned_text)
    date = _date_from_text(cleaned_text)
    destination_last4 = _destination_last4_from_text(cleaned_text)
    destination_name_matches = _destination_name_matches(cleaned_text)

    expected_last4 = _digits_only(RECEIPT_CARD_LAST4)[-4:]
    if expected_last4:
        destination_matches: bool | None = destination_last4 == expected_last4 if destination_last4 else False
    else:
        destination_matches = destination_name_matches

    keyword_score = _receipt_keyword_score(cleaned_text)
    is_receipt = keyword_score >= 2 or (amount is not None and tracking is not None)

    risk_flags: list[str] = []
    if not cleaned_text:
        risk_flags.append("متن فیش خوانده نشد")
    if not is_receipt:
        risk_flags.append("تصویر با اطمینان کافی به‌عنوان فیش شناسایی نشد")
    if amount is None:
        risk_flags.append("مبلغ تشخیص داده نشد")
    elif amount_matches is False:
        risk_flags.append("مبلغ با سفارش مطابقت ندارد")
    if not tracking:
        risk_flags.append("شماره پیگیری تشخیص داده نشد")
    if expected_last4 and destination_matches is False:
        risk_flags.append("کارت مقصد مطابقت ندارد یا خوانده نشد")
    if date is None:
        risk_flags.append("تاریخ یا ساعت تشخیص داده نشد")

    confidence = 15
    confidence += min(keyword_score * 8, 24)
    confidence += 22 if amount is not None else 0
    confidence += 16 if tracking else 0
    confidence += 10 if date else 0
    confidence += 13 if destination_matches is True else 0
    if amount_matches is False:
        confidence -= 20
    if not is_receipt:
        confidence -= 20
    confidence = max(0, min(100, confidence))

    if is_receipt and amount_matches is True and (destination_matches is not False):
        summary = "اطلاعات اصلی فیش با سفارش مطابقت اولیه دارد؛ تأیید نهایی پس از کنترل حساب بانکی انجام شود."
    elif not cleaned_text:
        summary = "OCR نتوانست متن قابل استفاده‌ای استخراج کند؛ بررسی دستی تصویر لازم است."
    else:
        summary = "برخی اطلاعات فیش ناقص یا نامطابق است؛ ادمین باید تصویر و گردش حساب را دستی بررسی کند."

    return {
        "is_receipt": is_receipt,
        "amount": amount,
        "date": date,
        "tracking_number": tracking,
        "destination_name": RECEIPT_ACCOUNT_HOLDER or None,
        "destination_card_last4": destination_last4,
        "confidence": confidence,
        "amount_matches": amount_matches,
        "destination_matches": destination_matches,
        "risk_flags": risk_flags,
        "summary": summary,
        "ocr_text": cleaned_text[:4000],
        "engine": f"tesseract:{OCR_LANG}",
        "raw": {},
    }


async def analyze_receipt(image_bytes: bytes, mime_type: str, expected_amount: int) -> dict[str, Any]:
    del mime_type  # Tesseract تصویر را از بایت‌ها تشخیص می‌دهد.
    try:
        text = await asyncio.to_thread(_ocr_sync, image_bytes)
    except RuntimeError as exc:
        if "timeout" in str(exc).lower():
            raise TimeoutError("زمان OCR بیش از حد مجاز شد.") from exc
        raise
    return analyze_ocr_text(text, int(expected_amount or 0))
