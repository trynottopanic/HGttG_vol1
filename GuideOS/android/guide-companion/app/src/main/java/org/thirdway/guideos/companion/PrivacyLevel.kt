package org.thirdway.guideos.companion

enum class PrivacyLevel {
    SENDER_ONLY,
    SHORT_PREVIEW,
    FULL_NOTIFICATION;

    companion object {
        fun fromStored(value: String?): PrivacyLevel =
            entries.firstOrNull { it.name == value } ?: SHORT_PREVIEW
    }
}
