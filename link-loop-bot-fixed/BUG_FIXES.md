# Bug-fix summary

## Fixed

### 1. Movie Rule repeated the same preview for every following video
A preview is now claimed once per pair/source-message through a database uniqueness boundary in `LoopState`.

Example:

```text
Post1 = image + text
Post2 = video   -> Post1 loops once
Post3 = video   -> ignored for the already-claimed Post1
Post4 = video   -> ignored for the already-claimed Post1
```

### 2. LoopEvent could not represent multiple created messages from the same source step
The old uniqueness shape blocked legitimate per-message event records. Events now include `loop_id` and `to_message_id`, so every created message can be recorded and recognized as bot-generated.

### 3. Bot-created reposts were inserted into the source cache before they were classified
The channel-post handler now checks both a short-lived in-process creation registry and persisted `LoopEvent` records **before** saving the message as a `PostUnit`. Reposted copies therefore cannot become future Movie Rule previews.

### 4. Albums larger than one Telegram media-group chunk lost bot-origin tracking
Outgoing albums are tracked for every created message across all chunks, not only the first created message.

### 5. A failed intermediate target could still allow downstream sends with invalid footer ancestry
Fan-out now stops after the first failed route hop. Successful earlier hops still get recoverable footer updates; downstream channels are not sent content that would reference a missing previous hop.

### 6. A 15-second footer delay was lost on process restart
Loop delivery state now persists `created_message_ids`, `footer_message_ids`, and `footer_ready_at`. Startup recovery resumes waiting/footer-failed work and marks interrupted running loops as failed instead of leaving them stuck forever.

### 7. Failed sends / footer edits could be marked `done`
Delivery status now differentiates `failed`, `waiting_footer`, `footer_failed`, and `done`.

### 8. Post-cache pruning could delete a post while its loop still needed it for footer generation
Active loop origins are protected from cache pruning until their delivery/footer workflow finishes.

### 9. Album collector used a one-shot timer
The inactivity timer now resets whenever another message from the same media group arrives, and a full 10-item group flushes immediately.

### 10. Telegram formatting, hidden links, and inline keyboards were lost during reposts
The saved post data now includes message entities, caption entities, and reply markup. Visible URL text is still stripped while hidden `text_link`/`text_mention` entities and normal formatting offsets are preserved. Album keyboards are restored after the media group is created.

### 11. Non-idempotent send calls were retried after ambiguous network errors
`sendMessage` / `sendMediaGroup` are now retried only for explicit Telegram flood-wait responses. Generic network errors are surfaced instead of being blindly retried, avoiding duplicate sends when Telegram accepted the original request but the response was lost.

### 12. Duplicate PostUnit creation could fail under concurrent processing
`save_post_unit()` now treats a unit-key uniqueness collision as an idempotent race and returns the already-created winner.

### 13. Local `.env` was not loaded automatically
`python-dotenv` is now loaded during configuration initialization.
