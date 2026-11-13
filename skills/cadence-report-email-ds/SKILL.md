---
name: cadence-report-email-ds
description: Draft (and, on the user's "send", send) the SEC DS monthly or quarterly report data-request email to Samsung DS ("SECDS) {M}월 월간 보고서 작성을 위한 파일 송부 요청"). Use when the user types /cadence-report-email-ds or asks to create the SECDS cadence report request email.
argument-hint: "[YYYY-MM] [monthly|quarterly] [이름] [Knox 메일]"
---

# SECDS cadence report — request email

Creates the Gmail draft of the data-request email, shows it, and sends it only when the user says **send**.

**Pre-authorized by the user for this skill:** creating the Gmail draft, deleting a draft this skill created (when rebuilding after an edit), and adding the Gmail label below. Do these without asking. **Sending always requires the user's explicit "send" in this conversation.** Never send any other email.

## 0. Who is sending

Find the signed-in Gmail address: `search_threads` with `in:sent` (pageSize 1). The `sender` of that message is the user's address.

- If it is `kisoon.kim@o9solutions.com`: use **sender name `김기순`** and **Knox email `kisoonk.kim@partner.samsung.com`**. Don't ask.
- Otherwise, ask the user in one message, then wait for the answer:
  > 메일 끝에 들어갈 **이름**(예: 홍길동)과, 사용자정보 파일을 받을 **Knox 메일 주소**(예: xxx@partner.samsung.com)를 알려주세요.
  - Use the name for the sign-off line (`{NAME} 드림`).
  - Use the Knox address in Cc **in place of** `kisoonk.kim@partner.samsung.com`.
  - Check that the Knox address looks like an email; if not, ask again.
  - If the user already gave both in `$ARGUMENTS` or earlier in this conversation, don't ask again.

## 1. Decide month and variant

All dates in **Asia/Seoul** (`TZ=Asia/Seoul date`).

- Reported month = the month in `$ARGUMENTS` if given (`YYYY-MM`), otherwise the **previous calendar month**.
- Variant = `quarterly` if `$ARGUMENTS` says so, or if no argument and the current month is Jan/Apr/Jul/Oct (the reported month is then the last month of the quarter just ended). Otherwise `monthly`. `monthly` in the arguments forces monthly.
- Names: `M` = month number (11), `Mon` = English abbreviation (Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec), `YYYY` / `YY` = year of the reported month, `q` = quarter number (1–4).

## 2. Duplicate check

Search Gmail `in:sent subject:"<subject>" newer_than:40d` and `list_drafts` with `subject:"<subject>"`. If it was already sent, say so with the link and stop. If a draft exists, show it and go to step 4 instead of creating another.

## 3. Create the draft

- **Subject**
  - monthly: `SECDS) {M}월 월간 보고서 작성을 위한 파일 송부 요청`
  - quarterly: `SECDS) {YY}Q{q} 분기 보고서 작성을 위한 파일 송부 요청`
- **To:** `jinpa.hong@samsung.com`, `s30515.kim@samsung.com`
- **Cc:** `{KNOX_EMAIL}`, `hjin356.kim@partner.samsung.com` (`{KNOX_EMAIL}` comes from step 0)
- **includeSignature:** true (adds the sender's own Gmail signature)
- **Inline image:** `assets/download_users.png` in this skill's folder → `attachments[0]` = `{content: "sha256:<hash>:<absolute path>", filename: "image.png", mimeType: "image/png", inline: true}` (get the hash with `sha256sum`). Attaching by reference fails for files under `~/.claude`; first copy the PNG to a working folder (e.g. `$(mktemp -d)` or the session scratchpad) and reference that copy. If the file is missing, download `download_users.png` from Drive folder `1c66vdOVBXuCckluDwoGs9GnxzFEnUTdf`.
- **htmlBody** — use exactly this text; only `{REPORT_NAME}`, `{ITEMS}` and `{NAME}` change:

```html
<div dir="ltr">
<div>안녕하세요 홍진파 프로님,</div>
<div><br></div>
<div>{REPORT_NAME} 작성에 필요한 파일 다운로드를 요청드립니다. </div>
<div>대상 정보는 운영 테넌트(SECDSPMIX, MEMBP, MEMLTP) 에서 아래의 NLP 수행 결과와 사용자 정보 다운로드이며, 기존에 제공해주신 자료와 동일한 양식으로 제공해주시면 감사하겠습니다.</div>
<div>권한 별 월간 사용량 정보를 추출하기 위해서, Email 주소가 필요하여, 사용자정보는 외부 반출이 불가능하기 때문에, Cc되어 있는 이메일로 제공해주시면 감사하겠습니다. </div>
<div><br></div>
<div><b>1. NLP 쿼리 후 파일 다운로드</b></div>
<div><font face="arial, sans-serif">{ITEMS}</font></div>
<div><br></div>
<div><b>2. 사용자정보 파일 다운로드</b></div>
<div>User Management WS &gt; Download Users</div>
<img src="cid:att0" alt="image.png" width="430" height="220">
<div><br></div>
<div>감사합니다.</div>
<div>{NAME} 드림</div>
</div>
```

- `{NAME}`: the sender name from step 0.
- `{REPORT_NAME}`: monthly `{YY}년 {M}월 월간 보고서` / quarterly `{YY}년 Q{q} 분기 보고서`
- `{ITEMS}` (joined with `<br>`):
  1. `1) top 1000 users usage duration for {Mon} in {YYYY}`
  2. `2) top 10 views by total hits for {Mon} in {YYYY}`
  3. `3) top 10 views by usage duration for {Mon} in {YYYY}`
  - quarterly only, also:
  4. `4) Quarterly Individual Users Usage Duration and Total Hits in last 3 months`
  5. `5) views by total hits in last 3 months`
  6. `6) views by usage duration in last 3 months`

Create it with Gmail `create_draft`.

## 4. Show it and ask

Reply in Korean in exactly this layout (fill in the values), then stop and wait for the answer:

```
📧 보고서 요청 메일 초안을 만들었습니다. 확인해 주세요.

보내는 사람: {NAME} ({sender Gmail address})
  · Knox 메일: {KNOX_EMAIL}
  · 김기순 계정이면 "(기본값)"을 붙이고, 아니면 "(입력하신 값)"을 붙입니다.

1. 월: {YYYY}년 {M}월
2. 구분: Monthly  (또는 Quarterly — {YY}Q{q})
3. Tenant: SECDSPMIX, MEMBP, MEMLTP
4. 받는 사람: jinpa.hong@samsung.com, s30515.kim@samsung.com
5. 참조: {KNOX_EMAIL}, hjin356.kim@partner.samsung.com

제목: {subject}
요청 항목: 1) … 3)  (Quarterly면 1) … 6))
초안 보기: {draft viewUrl}

**send** 라고 하시면 발송하고, **leave** 라고 하시면 초안으로 둡니다. 수정할 내용이 있으면 말씀해 주세요.
```

Values must come from the draft actually created (re-read it with `list_drafts` `DRAFT_VIEW_FULL` if unsure), not from memory.

## 5. On the user's answer

- **send / 보내 / 발송** → Gmail `send_message` with `draftId`. Then add the label `SECDS-Report/Awaiting-Reply` to the sent thread (`list_labels` to find its id; create it with `create_label` if missing) so the reply watcher picks it up. Confirm with the thread link.
- **leave / 두기** → keep the draft and confirm.
- **an edit** → create a new draft with the change (same inline image), delete the old draft, show it again, and ask again.
