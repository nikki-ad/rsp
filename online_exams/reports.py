from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features
from django.core.files.base import ContentFile
from core.jalali import jalali_format


def write_report(p):
    if not features.check("raqm"):
        raise RuntimeError("Pillow with libraqm is required for Persian exam reports")
    font_path = Path(__file__).parent / "fonts" / "DejaVuSans.ttf"
    font = ImageFont.truetype(str(font_path), 26)
    small = ImageFont.truetype(str(font_path), 23)
    questions = list(p.exam.questions.all())
    image = Image.new("RGB", (1200, 550 + 48 * len(questions)), "white")
    draw = ImageDraw.Draw(image)

    def line(text, y, fill="#183c35", font=font):
        text = str(text)
        while draw.textlength(text, font=font, direction="rtl") > 1100 and font.size > 18:
            font = ImageFont.truetype(str(font_path), font.size - 1)
        while draw.textlength(text, font=font, direction="rtl") > 1100:
            text = text[:-2] + "…"
        draw.text((1150, y), text, font=font, direction="rtl", language="fa", anchor="ra", fill=fill)

    line("کارنامه آزمون آنلاین — RSP", 35)
    line(p.exam.title[:70], 90)
    line("درس: " + p.exam.subject[:60], 135)
    line("دانش‌آموز: " + str(p.student)[:65], 180)
    line("کلاس: " + p.classroom_label[:65], 225)
    line("زمان ثبت: " + jalali_format(p.submitted_at, True) + " — به وقت تهران", 270)
    line(f"درصد: {p.percentage}٪    درست: {p.correct}    غلط: {p.wrong}    سفید: {p.blank}", 315)
    line("نمره منفی: " + ("هر سه غلط، یک درست" if p.exam.negative_marking else "ندارد"), 360)
    columns = [1050, 790, 530, 270]
    def row(values, y, fill):
        for x, text in zip(columns, values):
            draw.text((x, y), str(text), font=small, direction="rtl", language="fa", anchor="ma", fill=fill)
    draw.rectangle((90, 410, 1160, 458), fill="#e9f3ee")
    row(["شماره سؤال", "پاسخ دانش‌آموز", "کلید", "وضعیت"], 420, "#183c35")
    for index, question in enumerate(questions):
        answer = p.answers.get(str(question.number))
        status = "سفید" if answer is None else "درست" if answer == question.correct_option else "غلط"
        y = 470 + index * 48
        draw.line((90, y + 37, 1160, y + 37), fill="#dde8e1")
        row([question.number, answer or "—", question.correct_option, status], y,
            "#17653f" if status == "درست" else "#973c3c")
    data = BytesIO()
    image.save(data, format="PNG")
    p.report.save(f"{p.exam_id}/{p.pk}.png", ContentFile(data.getvalue()), save=True)
