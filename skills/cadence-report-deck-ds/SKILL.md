---
name: cadence-report-deck-ds
description: Build the "SEC DS_Monthly Report" Google Slides deck from Samsung DS's reply to the SECDS report data-request email - validate the attachments, analyze usage, copy last month's deck and update Section 1. Use when the user types /cadence-report-deck-ds or asks to make the SECDS monthly report slides.
argument-hint: "[YYYY-MM]"
---

# SECDS cadence report — build the deck

The user has already checked that the reply arrived. This skill validates it, analyzes the data and creates the new deck.

**Pre-authorized by the user for this skill:** Gmail labels (`label_thread`, `unlabel_thread`, `label_message`, `create_label`); Drive export/download of decks and files, `create_file` and `update_file` (upload the new deck, history CSV, renames). Do these without asking. Never send email, never delete or trash anything.

## Fixed locations

| What | ID |
|---|---|
| Report folder (decks) | Drive folder `1NfoOiZ_am9dZAtkpudrnK706zRfhJ9kc` |
| Automation folder (history CSVs) | Drive folder `1c66vdOVBXuCckluDwoGs9GnxzFEnUTdf` |
| Script | `scripts/build_report.py` in this skill's folder (needs `python-pptx`, `openpyxl`; `pip install` if missing) |

All dates in **Asia/Seoul**. Work dir: `W=$(mktemp -d)`, data in `$W/data`.

## 1. Find the reply

- Request thread: if `$ARGUMENTS` has `YYYY-MM`, the subject is `SECDS) {M}월 월간 보고서 작성을 위한 파일 송부 요청` (or the quarterly `SECDS) {YY}Q{q} 분기 보고서 …` when that month ends a quarter). Otherwise search `in:sent subject:"SECDS)" newer_than:45d` and take the newest request thread **without** the `SECDS-Report/Done` label.
- `get_thread`. Reply = newest message **not from the user** with `.xlsx`/`.csv` attachments. Reported month comes from the request subject (quarterly → the quarter's last month). If there is no such reply, say so and stop.

## 2. Download and validate

- `download_gmail_attachment` for every non-image attachment; copy each saved file to `$W/data/<original filename>` (the original name matters).
- `python3 <skill>/scripts/build_report.py validate --dir $W/data --month YYYY-MM [--quarterly]`
- Expected (monthly): 3 CSVs `o9.UsersForTenant_{SECDSPMIX|MEMBP|MEMLTP}_*.csv` and 9 xlsx `{pmix|bp|ltp}_{top_1000_users_usage_duration|top_10_views_by_total_hits|top_10_views_by_usage_duration}_for_{Mon}_in_{YYYY}.xlsx`. Quarterly adds the last-3-months files.
- **If it fails:** label the thread `SECDS-Report/Needs-Attention`, tell the user in Korean exactly which files are missing or wrong and which were received, and stop.
- If it passes, label the reply message `SECDS-Report/Checked`.

## 3. Template and history

- Template = deck for the **latest month before the reported month** in the report folder. Titles look like `SEC DS_Monthly Report (Aug. 2026)` or `(July. 2026)`; parse month and year, ignore titles containing `TEST`. Search with `parentId = '1NfoOiZ_am9dZAtkpudrnK706zRfhJ9kc' and mimeType = 'application/vnd.google-apps.presentation'`. Export it with `download_file_content`, `exportMimeType = application/vnd.openxmlformats-officedocument.presentationml.presentation` → `$W/template.pptx`.
- History = newest `history_YYYY-MM.csv` in the automation folder (ignore `OLD_*`) → `$W/history.csv`.
- Base date (기준일) = reply date in KST, `YYYY.MM.DD`.

## 4. Build

```
python3 <skill>/scripts/build_report.py build --dir $W/data --month YYYY-MM \
  --template $W/template.pptx --history $W/history.csv --history-out $W/history_new.csv \
  --base-date YYYY.MM.DD --out $W/report.pptx
```

What it does:
- **Section 1:** cover month/date, 3-month user and hours charts, Top-10 UI tables, and Role tables per tenant (roles from the template's tables) are updated.
- **Sections 2–4:** Batch, 서포트 티켓, and 환경별 테넌트 현황 are copied unchanged, with a red **"⚠ 업데이트 필요"** badge on each content slide.

## 5. Upload and verify

- Drive `create_file` in the report folder, `contentMimeType = application/vnd.openxmlformats-officedocument.presentationml.presentation` (converts to Google Slides), `base64Content = sha256:<hash>:<abs path of report.pptx>`. Title `SEC DS_Monthly Report ({Mon}. {YYYY})`; if that title already exists, append ` v2`.
- Upload `$W/history_new.csv` to the automation folder as `history_YYYY-MM.csv` (`contentMimeType: text/csv`, `disableConversionToGoogleType: true`). If that name already exists, rename the old one to `OLD_history_YYYY-MM.csv` first.
- Verify: export the new deck as PDF, render pages (`pdftoppm -r 40`) and look at slides 1 and 4–10. Check that charts show 3 months, tables are filled, and titles say `({M}월)`.
- Labels: remove `SECDS-Report/Awaiting-Reply` and `SECDS-Report/Needs-Attention`, then add `SECDS-Report/Done`.

## 6. Report (Korean)

Give the deck link, users and hours vs. last month, Top-1 UI, and the script's `warnings`. Remind the user that the 6 slides with "⚠ 업데이트 필요" still show last month's Batch / ticket / tenant content and must be updated by hand, with the badge deleted afterwards. If any step failed, say which one and why.
