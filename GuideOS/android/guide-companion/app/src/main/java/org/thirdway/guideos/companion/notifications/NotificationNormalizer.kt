package org.thirdway.guideos.companion.notifications

import android.app.Notification
import android.os.Build
import android.os.Parcelable
import android.service.notification.StatusBarNotification
import org.thirdway.guideos.companion.PrivacyLevel
import org.thirdway.guideos.companion.events.GuideMessageEvent
import org.thirdway.guideos.companion.events.TextSanitizer
import java.nio.charset.StandardCharsets
import java.security.MessageDigest

object NotificationNormalizer {
    private const val EVENT_LIFETIME_MILLIS = 10 * 60 * 1000L

    fun normalize(sbn: StatusBarNotification, privacy: PrivacyLevel): GuideMessageEvent? {
        val notification = sbn.notification
        if ((notification.flags and Notification.FLAG_GROUP_SUMMARY) != 0) return null

        val extras = notification.extras
        val latestMessage = if (Build.VERSION.SDK_INT >= 30) {
            val messageBundles = if (Build.VERSION.SDK_INT >= 33) {
                extras.getParcelableArray(Notification.EXTRA_MESSAGES, Parcelable::class.java)
            } else {
                @Suppress("DEPRECATION")
                extras.getParcelableArray(Notification.EXTRA_MESSAGES)
            }
            Notification.MessagingStyle.Message.getMessagesFromBundleArray(
                messageBundles,
            ).lastOrNull()
        } else {
            null
        }
        val messageSender = if (Build.VERSION.SDK_INT >= 28) {
            latestMessage?.senderPerson?.name
        } else {
            @Suppress("DEPRECATION")
            latestMessage?.sender
        }

        val sender = TextSanitizer.clean(
            messageSender ?: extras.getCharSequence(Notification.EXTRA_TITLE),
            80,
        ) ?: "Discord"
        val conversation = TextSanitizer.clean(
            extras.getCharSequence(Notification.EXTRA_CONVERSATION_TITLE),
            120,
        )
        val fullText = TextSanitizer.clean(
            latestMessage?.text
                ?: extras.getCharSequence(Notification.EXTRA_BIG_TEXT)
                ?: extras.getCharSequence(Notification.EXTRA_TEXT),
            512,
        )
        val preview = when (privacy) {
            PrivacyLevel.SENDER_ONLY -> null
            PrivacyLevel.SHORT_PREVIEW -> fullText?.take(120)
            PrivacyLevel.FULL_NOTIFICATION -> fullText
        }
        val contentState = when {
            privacy == PrivacyLevel.SENDER_ONLY -> "hidden"
            preview == null -> "unavailable"
            privacy == PrivacyLevel.SHORT_PREVIEW && fullText != preview -> "preview"
            else -> "full"
        }
        val occurredAt = sbn.postTime
        val eventId = digest("${sbn.key}|$occurredAt|$sender|${fullText.orEmpty()}")

        return GuideMessageEvent(
            eventId = eventId,
            occurredAtMillis = occurredAt,
            expiresAtMillis = occurredAt + EVENT_LIFETIME_MILLIS,
            sender = sender,
            conversation = conversation,
            preview = preview,
            contentState = contentState,
        )
    }

    private fun digest(value: String): String = MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray(StandardCharsets.UTF_8))
        .joinToString("") { "%02x".format(it) }
}
