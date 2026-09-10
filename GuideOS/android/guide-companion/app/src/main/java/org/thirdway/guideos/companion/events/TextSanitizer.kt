package org.thirdway.guideos.companion.events

object TextSanitizer {
    private val unsafeControlCharacters = Regex("[\\u0000-\\u0008\\u000B\\u000C\\u000E-\\u001F\\u007F]")
    private val repeatedWhitespace = Regex("[ \\t\\x0B\\f\\r]+")

    fun clean(value: CharSequence?, maximumLength: Int): String? {
        val cleaned = value
            ?.toString()
            ?.replace(unsafeControlCharacters, "")
            ?.replace(repeatedWhitespace, " ")
            ?.trim()
            ?.take(maximumLength)
            .orEmpty()
        return cleaned.ifBlank { null }
    }
}
