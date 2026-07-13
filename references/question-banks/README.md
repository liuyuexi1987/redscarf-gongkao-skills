# Question Bank Interface

This public package does not bundle question-bank content. The project ships no built-in exam question bank; `总题库.md` is an empty template. All questions come from user uploads.

Question banks are optional user data. They are used for practice, auto-grading, and spaced review, but they are not required for the method libraries or the review engine to work.

## How To Add Your Own Bank

1. Append user-imported questions to `总题库.md`.
2. Keep the import report in the `导入记录 / Import Log` table inside `总题库.md`.
3. Only enable auto-grading when every question has a verified answer.

## Automatic Import Layer

When the user says "把这页加入题库", "把这张图加入题库", "把这个 PDF 加入题库", "把这个 doc 加入题库", "导入题库", or similar, append only eligible structured results to `总题库.md`; skipped visual-dependent items are recorded only in the import log.

The import layer is a **thin automation layer**: it only extracts text/OCR, splits questions, detects answers, marks verification status, saves Markdown, and writes a short report inside `总题库.md`. It must not explain, review, quiz, write error cards, or auto-grade by default.

**Differentiate from "看错题页/讲错题"**: import = storage only; "帮我看错题页/讲错题/复盘这页" = may explain and write error cards, but must not auto-set unverified questions as `可自动判题: true`.

## Visual-Dependent Question Boundary

- Before writing a question, decide whether it can be reproduced completely as text or a Markdown table.
- Graphic reasoning, spatial figures, image-based options, and other questions that require the original image are not appended to `Questions`. Being visible in the current chat does not make the image persistently reusable.
- Data-analysis charts may be stored only when every necessary value, label, legend, year, unit, stem, and option has been completely and verifiably transcribed. Otherwise skip the question instead of saving a damaged OCR version.
- Record skipped counts and reasons in the import log. Skipped visual questions are not counted as pending questions, and the report states only the question type and skip reason rather than reconstructing graphic details. Do not create a pending question block for an item that cannot be answered without its missing image.
- For skipped visual questions, `recognized answer count` includes only answers explicitly visible in the source or a verified answer page. A model-inferred option is not a recognized answer.
- A skipped visual question may still be explained or reviewed while the user is currently providing the image; later review uses the related method workflow rather than a reconstructed original question.

## Per-Question Metadata

Every imported question must include:

| Field | Default | Description |
|---|---|---|
| `batch_id` | — | Import batch identifier |
| `question_id` | — | Sequential within batch |
| `source_user_provided` | `true` | Always true for user imports |
| `source_type` | — | `photo` / `pdf` / `doc` / `manual` |
| `来源声明` | `用户上传` | Provenance |
| `使用范围` | `个人复习` | Usage scope |
| `状态` | `待核对` | Verification status |
| `可自动判题` | `false` | Auto-grade eligible |
| `答案核验` | `未核验` | Answer verification |
| `核对备注` | — | Verification notes |

## Fail-Closed Rule

ALL imported questions start with fail-closed defaults:

- `状态: 待核对`
- `可自动判题: false`
- `答案核验: 未核验`

Set `可自动判题: true` only when ALL are true: stem complete, options complete (MCQ), answer explicit and unambiguous, question/answer count match, no OCR doubts.

If an answer is missing, uncertain, OCR-derived but unverified, or mismatched with the question count, keep an otherwise reproducible text/table question at `可自动判题: false` and `状态: 待核对`. If the question itself depends on a missing or non-persistent image, do not append it.

**Only `可自动判题: true` AND `答案核验: 已核验` questions may enter "考我" auto-grading.**

The agent may still use reproducible unverified material for reading, manual review, or pending storage, but it must not grade the user automatically.
