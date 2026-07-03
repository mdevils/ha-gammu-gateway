/**
 * Custom Lovelace cards for the SMS Gammu Gateway integration.
 *
 *  - gammu-send-card:     a form that sends an SMS via the send_sms service.
 *  - gammu-messages-card: a list of received/sent messages read from the
 *                         "SMS Messages" sensor attributes.
 *
 * Dependency-free vanilla custom elements (no build step required).
 */

const STYLE = `
  :host { display: block; }
  ha-card { padding: 16px; }
  .header {
    font-size: 1.2rem;
    font-weight: 500;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .header ha-icon { color: var(--primary-color); }
  .field { margin-bottom: 12px; }
  label {
    display: block;
    font-size: 0.85rem;
    color: var(--secondary-text-color);
    margin-bottom: 4px;
  }
  input, textarea {
    width: 100%;
    box-sizing: border-box;
    padding: 8px 10px;
    border: 1px solid var(--divider-color, #ccc);
    border-radius: 8px;
    background: var(--card-background-color, #fff);
    color: var(--primary-text-color);
    font-family: inherit;
    font-size: 1rem;
  }
  textarea { resize: vertical; min-height: 72px; }
  .row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  button.primary {
    background: var(--primary-color);
    color: var(--text-primary-color, #fff);
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 1rem;
    cursor: pointer;
  }
  button.primary:disabled { opacity: 0.6; cursor: default; }
  button.link {
    background: none;
    border: none;
    color: var(--primary-color);
    cursor: pointer;
    font-size: 0.85rem;
    padding: 4px;
  }
  .counter { font-size: 0.8rem; color: var(--secondary-text-color); }
  .status { margin-top: 8px; font-size: 0.9rem; min-height: 1.2em; }
  .status.ok { color: var(--success-color, #2e7d32); }
  .status.err { color: var(--error-color, #c62828); }

  .messages { display: flex; flex-direction: column; gap: 8px; max-height: 420px; overflow-y: auto; }
  .empty { color: var(--secondary-text-color); text-align: center; padding: 16px 0; }
  .msg {
    display: flex;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 10px;
    background: var(--secondary-background-color, #f5f5f5);
  }
  .msg.outbound { background: color-mix(in srgb, var(--primary-color) 12%, transparent); }
  .msg ha-icon { flex: 0 0 auto; color: var(--secondary-text-color); }
  .msg.outbound ha-icon { color: var(--primary-color); }
  .msg .body { flex: 1 1 auto; min-width: 0; }
  .msg .meta {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    font-size: 0.8rem;
    color: var(--secondary-text-color);
  }
  .msg .number { font-weight: 500; color: var(--primary-text-color); }
  .msg .text { white-space: pre-wrap; word-break: break-word; margin-top: 2px; }
  .msg .del { flex: 0 0 auto; }
`;

function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

class GammuSendCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
  }

  getCardSize() {
    return 3;
  }

  static getStubConfig() {
    return { title: "Send SMS" };
  }

  _render() {
    if (this._rendered) return;
    this._rendered = true;
    this.attachShadow({ mode: "open" });
    const title = this._config.title || "Send SMS";
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <div class="header"><ha-icon icon="mdi:message-plus"></ha-icon><span>${escapeHtml(
          title
        )}</span></div>
        <div class="field">
          <label>To</label>
          <input id="number" type="tel" placeholder="+15551234567"
            value="${escapeHtml(this._config.default_number || "")}" />
        </div>
        <div class="field">
          <label>Message</label>
          <textarea id="message" placeholder="Type your message…"></textarea>
        </div>
        <div class="row">
          <span class="counter" id="counter">0 chars</span>
          <button class="primary" id="send">Send</button>
        </div>
        <div class="status" id="status"></div>
      </ha-card>
    `;

    this._number = this.shadowRoot.getElementById("number");
    this._message = this.shadowRoot.getElementById("message");
    this._button = this.shadowRoot.getElementById("send");
    this._status = this.shadowRoot.getElementById("status");
    this._counter = this.shadowRoot.getElementById("counter");

    this._message.addEventListener("input", () => this._updateCounter());
    this._button.addEventListener("click", () => this._send());
  }

  _updateCounter() {
    const len = this._message.value.length;
    const parts = len === 0 ? 0 : Math.ceil(len / 160);
    this._counter.textContent = `${len} chars${parts > 1 ? ` · ${parts} SMS` : ""}`;
  }

  _setStatus(text, kind) {
    this._status.textContent = text;
    this._status.className = `status ${kind || ""}`;
  }

  async _send() {
    if (!this._hass) return;
    const number = this._number.value.trim();
    const message = this._message.value;
    if (!number) {
      this._setStatus("Please enter a recipient number.", "err");
      return;
    }
    if (!message.trim()) {
      this._setStatus("Please enter a message.", "err");
      return;
    }

    const data = { number, message };
    if (this._config.entry_id) data.entry_id = this._config.entry_id;

    this._button.disabled = true;
    this._setStatus("Sending…", "");
    try {
      await this._hass.callService("gammu_gateway", "send_sms", data);
      this._setStatus(`Sent to ${number}.`, "ok");
      this._message.value = "";
      this._updateCounter();
    } catch (err) {
      this._setStatus(`Failed: ${err && err.message ? err.message : err}`, "err");
    } finally {
      this._button.disabled = false;
    }
  }
}

class GammuMessagesCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("You need to define an 'entity' (the SMS Messages sensor).");
    }
    this._config = config;
    this._lastSignature = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 6;
  }

  static getStubConfig(hass) {
    let entity = "";
    if (hass && hass.states) {
      entity =
        Object.keys(hass.states).find(
          (id) =>
            id.startsWith("sensor.") &&
            Array.isArray(hass.states[id].attributes.messages)
        ) || "";
    }
    return { entity, title: "SMS Messages" };
  }

  _render() {
    this.attachShadow({ mode: "open" });
    const title = this._config.title || "SMS Messages";
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <div class="header">
          <ha-icon icon="mdi:message-text"></ha-icon><span>${escapeHtml(title)}</span>
          <span style="flex:1"></span>
          <button class="link" id="clear">Clear all</button>
        </div>
        <div class="messages" id="messages"></div>
      </ha-card>
    `;
    this._list = this.shadowRoot.getElementById("messages");
    this.shadowRoot.getElementById("clear").addEventListener("click", () => this._clear());
  }

  _stateObj() {
    return this._hass && this._hass.states
      ? this._hass.states[this._config.entity]
      : undefined;
  }

  _update() {
    const stateObj = this._stateObj();
    const all =
      stateObj && Array.isArray(stateObj.attributes.messages)
        ? stateObj.attributes.messages
        : [];

    const limit = parseInt(this._config.limit, 10);
    const messages = Number.isFinite(limit) && limit > 0 ? all.slice(0, limit) : all;

    const signature = messages.map((m) => m.id).join(",");
    if (signature === this._lastSignature) return;
    this._lastSignature = signature;

    if (!stateObj) {
      this._list.innerHTML = `<div class="empty">Entity '${escapeHtml(
        this._config.entity
      )}' not found.</div>`;
      return;
    }
    if (messages.length === 0) {
      this._list.innerHTML = `<div class="empty">No messages yet.</div>`;
      return;
    }

    this._list.innerHTML = messages
      .map((m) => {
        const outbound = m.direction === "outbound";
        const icon = outbound ? "mdi:arrow-up-bold-circle" : "mdi:arrow-down-bold-circle";
        return `
          <div class="msg ${outbound ? "outbound" : "inbound"}">
            <ha-icon icon="${icon}"></ha-icon>
            <div class="body">
              <div class="meta">
                <span class="number">${escapeHtml(m.number || "Unknown")}</span>
                <span>${escapeHtml(m.date || "")}</span>
              </div>
              <div class="text">${escapeHtml(m.text || "")}</div>
            </div>
            <button class="link del" data-id="${escapeHtml(m.id)}" title="Delete">✕</button>
          </div>
        `;
      })
      .join("");

    this._list.querySelectorAll("button.del").forEach((btn) => {
      btn.addEventListener("click", () =>
        this._delete(parseInt(btn.getAttribute("data-id"), 10))
      );
    });
  }

  _serviceData(extra) {
    const data = Object.assign({}, extra);
    if (this._config.entry_id) data.entry_id = this._config.entry_id;
    return data;
  }

  async _delete(id) {
    if (!this._hass || Number.isNaN(id)) return;
    this._lastSignature = null; // force re-render after change
    await this._hass.callService(
      "gammu_gateway",
      "delete_message",
      this._serviceData({ message_id: id })
    );
  }

  async _clear() {
    if (!this._hass) return;
    this._lastSignature = null;
    await this._hass.callService("gammu_gateway", "clear_messages", this._serviceData({}));
  }
}

customElements.define("gammu-send-card", GammuSendCard);
customElements.define("gammu-messages-card", GammuMessagesCard);

window.customCards = window.customCards || [];
window.customCards.push(
  {
    type: "gammu-send-card",
    name: "Gammu: Send SMS",
    description: "A form to send an SMS through the Gammu gateway.",
  },
  {
    type: "gammu-messages-card",
    name: "Gammu: SMS Messages",
    description: "A list of received and sent SMS messages.",
  }
);

console.info("%c GAMMU-GATEWAY-CARDS %c loaded ", "background:#03a9f4;color:#fff", "");
