const { Telegraf } = require("telegraf");
const axios = require("axios");
const crypto = require("crypto");
const http = require("http");

// ===== Env =====
const BOT_TOKEN = (process.env.TELEGRAM_BOT_TOKEN || "").trim();
const UPSTREAM_URL = (process.env.UPSTREAM_URL || "").trim();
const TIMEOUT_MS = parseInt(process.env.UPSTREAM_TIMEOUT_MS || "30000", 10);
const TELEGRAM_MODE = (process.env.TELEGRAM_MODE || "polling").trim().toLowerCase();

// Webhook-specific (only used when TELEGRAM_MODE=webhook)
const WEBHOOK_DOMAIN = (process.env.WEBHOOK_DOMAIN || "").trim();   // e.g. https://telegram.platform.ibbytech.com
const WEBHOOK_PATH   = (process.env.WEBHOOK_PATH || "/webhook").trim();
const WEBHOOK_PORT   = parseInt(process.env.WEBHOOK_PORT || "3000", 10);

// Outbound send API — shared secret for /send endpoint
// Set SEND_SECRET in .env. shogun-core must send X-Send-Secret header.
// Leave empty to disable auth (not recommended outside dev).
const SEND_SECRET    = (process.env.SEND_SECRET || "").trim();
const SEND_API_PORT  = parseInt(process.env.SEND_API_PORT || "3001", 10);

// Capability flags forwarded to upstream for policy decisions
const CAP_CAN_SEARCH      = (process.env.CAP_CAN_SEARCH      || "false").trim().toLowerCase() === "true";
const CAP_CAN_SCRAPE      = (process.env.CAP_CAN_SCRAPE      || "false").trim().toLowerCase() === "true";
const CAP_CAN_FETCH_FILES = (process.env.CAP_CAN_FETCH_FILES || "false").trim().toLowerCase() === "true";

// Allowlists
const ALLOWED_USER_IDS = (process.env.ALLOWED_USER_IDS || "")
  .split(",").map((s) => s.trim()).filter(Boolean);
const ALLOWED_GROUP_IDS = (process.env.ALLOWED_GROUP_IDS || "")
  .split(",").map((s) => s.trim()).filter(Boolean);

// ===== Guards =====
if (!BOT_TOKEN)      { console.error("FATAL: TELEGRAM_BOT_TOKEN missing"); process.exit(1); }
if (!UPSTREAM_URL)   { console.error("FATAL: UPSTREAM_URL missing");        process.exit(1); }
if (ALLOWED_USER_IDS.length === 0) { console.error("FATAL: ALLOWED_USER_IDS empty"); process.exit(1); }
if (TELEGRAM_MODE === "webhook" && !WEBHOOK_DOMAIN) {
  console.error("FATAL: WEBHOOK_DOMAIN required when TELEGRAM_MODE=webhook");
  process.exit(1);
}

// ===== Helpers =====
function nowIso() { return new Date().toISOString(); }
function mkId()   { return crypto.randomBytes(8).toString("hex"); }
function clip(s, n = 3500) {
  const str = String(s ?? "");
  return str.length > n ? str.slice(0, n) : str;
}

function isAllowedByParts({ from, chat }) {
  const userId   = from?.id   ? String(from.id)   : null;
  const chatId   = chat?.id   ? String(chat.id)   : null;
  const chatType = chat?.type;
  const userOk   = userId && ALLOWED_USER_IDS.includes(userId);

  if (chatType === "private") return !!userOk;
  if (chatType === "group" || chatType === "supergroup") {
    const groupOk = chatId && ALLOWED_GROUP_IDS.includes(chatId);
    return !!(userOk && groupOk);
  }
  return false;
}

function isAllowedCtx(ctx) {
  return isAllowedByParts({ from: ctx.from, chat: ctx.chat });
}

async function forward(envelope) {
  const resp = await axios.post(UPSTREAM_URL, envelope, {
    timeout: TIMEOUT_MS,
    headers: { "Content-Type": "application/json" },
  });
  return resp.data;
}

function baseEnvelopeFromCtx(ctx, kind) {
  return {
    receipt_id:  mkId(),
    received_at: nowIso(),
    kind,
    update:  { update_id: ctx.update?.update_id },
    from: {
      user_id:       ctx.from?.id,
      username:      ctx.from?.username,
      first_name:    ctx.from?.first_name,
      last_name:     ctx.from?.last_name,
      language_code: ctx.from?.language_code,
    },
    chat: {
      id:    ctx.chat?.id,
      type:  ctx.chat?.type,
      title: ctx.chat?.title,
    },
    message: {
      message_id:          ctx.message?.message_id,
      date:                ctx.message?.date,
      reply_to_message_id: ctx.message?.reply_to_message?.message_id,
    },
    capabilities: {
      can_search:      CAP_CAN_SEARCH,
      can_scrape:      CAP_CAN_SCRAPE,
      can_fetch_files: CAP_CAN_FETCH_FILES,
    },
    payload: {},
  };
}

function locationPayloadFromLoc(loc) {
  return loc ? {
    location: {
      latitude:               loc.latitude,
      longitude:              loc.longitude,
      horizontal_accuracy:    loc.horizontal_accuracy,
      live_period:            loc.live_period,
      heading:                loc.heading,
      proximity_alert_radius: loc.proximity_alert_radius,
    },
  } : { location: null };
}

function photoPayload(msg) {
  const photos = Array.isArray(msg?.photo) ? msg.photo : [];
  return {
    caption: msg?.caption || "",
    photos: photos.map((p) => ({
      file_id:        p.file_id,
      file_unique_id: p.file_unique_id,
      width:          p.width,
      height:         p.height,
      file_size:      p.file_size,
    })),
  };
}

function documentPayload(msg) {
  const d = msg?.document;
  return {
    caption: msg?.caption || "",
    document: d ? {
      file_id:        d.file_id,
      file_unique_id: d.file_unique_id,
      file_name:      d.file_name,
      mime_type:      d.mime_type,
      file_size:      d.file_size,
    } : null,
  };
}

function voicePayload(msg) {
  const v = msg?.voice;
  return {
    voice: v ? {
      file_id:        v.file_id,
      file_unique_id: v.file_unique_id,
      duration:       v.duration,
      mime_type:      v.mime_type,
      file_size:      v.file_size,
    } : null,
  };
}

// ===== Bot =====
const bot = new Telegraf(BOT_TOKEN);

// NOTE: No bot.command() handlers here — all slash commands (/status, /help, etc.)
// are forwarded to upstream (shogun-core) as kind=text envelopes.
// Gateway health is available via GET /health on the send API port.

bot.on("text", async (ctx) => {
  if (!isAllowedCtx(ctx)) return;
  const env = baseEnvelopeFromCtx(ctx, "text");
  env.payload = { text: ctx.message?.text || "", entities: ctx.message?.entities || [] };
  try {
    const upstream = await forward(env);
    if (upstream?.reply_text) return ctx.reply(clip(upstream.reply_text));
    return ctx.reply(`✅ Received. Receipt: ${env.receipt_id}`);
  } catch {
    return ctx.reply(`⚠️ Upstream unavailable. Receipt: ${env.receipt_id}`);
  }
});

bot.on("location", async (ctx) => {
  if (!isAllowedCtx(ctx)) return;
  const env = baseEnvelopeFromCtx(ctx, "location");
  env.payload = locationPayloadFromLoc(ctx.message?.location);
  try {
    const upstream = await forward(env);
    if (upstream?.reply_text) return ctx.reply(clip(upstream.reply_text));
    return ctx.reply(`✅ Location received. Receipt: ${env.receipt_id}`);
  } catch {
    return ctx.reply(`✅ Location received. Receipt: ${env.receipt_id}`);
  }
});

bot.on("photo", async (ctx) => {
  if (!isAllowedCtx(ctx)) return;
  const env = baseEnvelopeFromCtx(ctx, "photo");
  env.payload = photoPayload(ctx.message);
  try {
    const upstream = await forward(env);
    if (upstream?.reply_text) return ctx.reply(clip(upstream.reply_text));
    return ctx.reply(`✅ Photo received. Receipt: ${env.receipt_id}`);
  } catch {
    return ctx.reply(`✅ Photo received. Receipt: ${env.receipt_id}`);
  }
});

bot.on("document", async (ctx) => {
  if (!isAllowedCtx(ctx)) return;
  const env = baseEnvelopeFromCtx(ctx, "document");
  env.payload = documentPayload(ctx.message);
  try {
    const upstream = await forward(env);
    if (upstream?.reply_text) return ctx.reply(clip(upstream.reply_text));
    return ctx.reply(`✅ Document received. Receipt: ${env.receipt_id}`);
  } catch {
    return ctx.reply(`✅ Document received. Receipt: ${env.receipt_id}`);
  }
});

bot.on("voice", async (ctx) => {
  if (!isAllowedCtx(ctx)) return;
  const env = baseEnvelopeFromCtx(ctx, "voice");
  env.payload = voicePayload(ctx.message);
  try {
    const upstream = await forward(env);
    if (upstream?.reply_text) return ctx.reply(clip(upstream.reply_text));
    return ctx.reply(`✅ Voice received. Receipt: ${env.receipt_id}`);
  } catch {
    return ctx.reply(`✅ Voice received. Receipt: ${env.receipt_id}`);
  }
});

/**
 * Live location updates arrive as edited_message events.
 * We forward them as kind=location envelopes.
 * We do NOT auto-reply — only reply if upstream explicitly returns reply_text.
 */
bot.on("edited_message", async (ctx) => {
  const edited = ctx.update?.edited_message;
  if (!edited) return;
  if (!isAllowedByParts({ from: edited.from, chat: edited.chat })) return;

  if (edited.location) {
    const env = {
      receipt_id:  mkId(),
      received_at: nowIso(),
      kind: "location",
      update:  { update_id: ctx.update?.update_id },
      from: {
        user_id:       edited.from?.id,
        username:      edited.from?.username,
        first_name:    edited.from?.first_name,
        last_name:     edited.from?.last_name,
        language_code: edited.from?.language_code,
      },
      chat: {
        id:    edited.chat?.id,
        type:  edited.chat?.type,
        title: edited.chat?.title,
      },
      message: {
        message_id: edited.message_id,
        date:       edited.date,
        edit_date:  edited.edit_date,
      },
      capabilities: {
        can_search:      CAP_CAN_SEARCH,
        can_scrape:      CAP_CAN_SCRAPE,
        can_fetch_files: CAP_CAN_FETCH_FILES,
      },
      payload: locationPayloadFromLoc(edited.location),
    };

    try {
      const upstream = await forward(env);
      if (upstream?.reply_text && edited.chat?.id) {
        await bot.telegram.sendMessage(edited.chat.id, clip(upstream.reply_text));
      }
    } catch {
      // silent on live-location edit failures
    }
  }
});


// ===== Outbound Send API =====
//
// HTTP server on SEND_API_PORT (default 3001).
// Exposes two endpoints:
//
//   GET  /health  — liveness check, returns gateway mode and uptime
//   POST /send    — push a message to any allowed Telegram chat
//
// Auth: If SEND_SECRET is set, callers must include header:
//   X-Send-Secret: <value>
//
// POST /send request body:
//   { "chat_id": "123456789", "text": "Hello", "parse_mode": "Markdown" }
//
// parse_mode is optional. Supported values: "Markdown", "MarkdownV2", "HTML"
//
// POST /send response:
//   { "ok": true,  "message_id": 99 }
//   { "ok": false, "error": "..." }
//
// This endpoint is on platform_net only. shogun-core reaches it via
// https://telegram.platform.ibbytech.com/send (through Traefik).

const sendServer = http.createServer((req, res) => {
  res.setHeader("Content-Type", "application/json");

  // ── GET /health ──────────────────────────────────────────────────────────
  if (req.method === "GET" && req.url === "/health") {
    res.writeHead(200);
    res.end(JSON.stringify({
      ok:      true,
      mode:    TELEGRAM_MODE,
      uptime:  process.uptime(),
    }));
    return;
  }

  // ── POST /send ───────────────────────────────────────────────────────────
  if (req.method === "POST" && req.url === "/send") {
    // Shared-secret auth
    if (SEND_SECRET) {
      const provided = (req.headers["x-send-secret"] || "").trim();
      if (provided !== SEND_SECRET) {
        res.writeHead(401);
        res.end(JSON.stringify({ ok: false, error: "unauthorized" }));
        return;
      }
    }

    let body = "";
    req.on("data", (chunk) => { body += chunk; });
    req.on("end", async () => {
      try {
        const { chat_id, text, parse_mode } = JSON.parse(body);

        if (!chat_id || !text) {
          res.writeHead(400);
          res.end(JSON.stringify({ ok: false, error: "chat_id and text are required" }));
          return;
        }

        const opts = {};
        if (parse_mode) opts.parse_mode = parse_mode;

        const result = await bot.telegram.sendMessage(chat_id, clip(text), opts);
        console.log(`[send] chat_id=${chat_id} message_id=${result.message_id}`);
        res.writeHead(200);
        res.end(JSON.stringify({ ok: true, message_id: result.message_id }));

      } catch (err) {
        console.error(`[send] error: ${err.message}`);
        res.writeHead(500);
        res.end(JSON.stringify({ ok: false, error: err.message }));
      }
    });
    return;
  }

  // ── 404 ──────────────────────────────────────────────────────────────────
  res.writeHead(404);
  res.end(JSON.stringify({ ok: false, error: "not found" }));
});

sendServer.listen(SEND_API_PORT, "0.0.0.0", () => {
  console.log(`send API listening on :${SEND_API_PORT}`);
});


// ===== Launch =====
async function start() {
  if (TELEGRAM_MODE === "webhook") {
    console.log(`Starting in webhook mode: ${WEBHOOK_DOMAIN}${WEBHOOK_PATH} (port ${WEBHOOK_PORT})`);
    await bot.launch({
      webhook: {
        domain:   WEBHOOK_DOMAIN,
        hookPath: WEBHOOK_PATH,
        port:     WEBHOOK_PORT,
      },
    });
  } else {
    console.log("Starting in polling mode");
    await bot.launch();
  }
  console.log("gateway ready");
}

start().catch((err) => {
  console.error("launch failed:", err?.message || err);
  process.exit(1);
});

process.once("SIGINT",  () => bot.stop("SIGINT"));
process.once("SIGTERM", () => bot.stop("SIGTERM"));
