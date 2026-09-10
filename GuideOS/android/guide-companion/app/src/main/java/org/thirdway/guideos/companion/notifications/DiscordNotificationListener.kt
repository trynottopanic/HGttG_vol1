package org.thirdway.guideos.companion.notifications

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import org.thirdway.guideos.companion.CompanionPreferences
import org.thirdway.guideos.companion.events.EventPipeline
import java.util.concurrent.Executors

class DiscordNotificationListener : NotificationListenerService() {
    private val worker = Executors.newSingleThreadExecutor()

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        // Check the package before reading any notification content. Android grants the
        // listener broad access, but Guide Companion deliberately observes Discord only.
        if (sbn.packageName != DISCORD_PACKAGE) return

        val preferences = CompanionPreferences(applicationContext)
        if (!preferences.discordForwardingEnabled) return
        val privacy = preferences.privacyLevel

        worker.execute {
            NotificationNormalizer.normalize(sbn, privacy)?.let(EventPipeline::accept)
        }
    }

    override fun onDestroy() {
        worker.shutdownNow()
        super.onDestroy()
    }

    companion object {
        const val DISCORD_PACKAGE = "com.discord"
    }
}
