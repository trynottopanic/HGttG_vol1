package org.thirdway.guideos.companion

import android.content.Context

class CompanionPreferences(context: Context) {
    private val values = context.getSharedPreferences("guide_companion", Context.MODE_PRIVATE)

    var discordForwardingEnabled: Boolean
        get() = values.getBoolean(KEY_DISCORD_ENABLED, false)
        set(value) = values.edit().putBoolean(KEY_DISCORD_ENABLED, value).apply()

    var privacyLevel: PrivacyLevel
        get() = PrivacyLevel.fromStored(values.getString(KEY_PRIVACY_LEVEL, null))
        set(value) = values.edit().putString(KEY_PRIVACY_LEVEL, value.name).apply()

    companion object {
        private const val KEY_DISCORD_ENABLED = "discord_forwarding_enabled"
        private const val KEY_PRIVACY_LEVEL = "privacy_level"
    }
}
