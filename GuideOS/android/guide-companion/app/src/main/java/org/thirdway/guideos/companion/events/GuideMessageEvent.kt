package org.thirdway.guideos.companion.events

import org.json.JSONObject

data class GuideMessageEvent(
    val eventId: String,
    val occurredAtMillis: Long,
    val expiresAtMillis: Long,
    val sender: String,
    val conversation: String?,
    val preview: String?,
    val contentState: String,
) {
    fun toJson(): JSONObject = JSONObject()
        .put("protocol", "guide-event/1")
        .put("type", "message.received")
        .put("capability", "phone.notifications.discord.observe")
        .put("event_id", eventId)
        .put("occurred_at_ms", occurredAtMillis)
        .put("expires_at_ms", expiresAtMillis)
        .put("source", JSONObject()
            .put("kind", "android.notification")
            .put("application", "discord"))
        .put("message", JSONObject()
            .put("sender", sender)
            .put("conversation", conversation ?: JSONObject.NULL)
            .put("preview", preview ?: JSONObject.NULL)
            .put("content_state", contentState))
}
