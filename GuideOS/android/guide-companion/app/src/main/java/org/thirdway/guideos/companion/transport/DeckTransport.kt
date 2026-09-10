package org.thirdway.guideos.companion.transport

import org.thirdway.guideos.companion.events.GuideMessageEvent

interface DeckTransport {
    val state: String
    fun offer(event: GuideMessageEvent)
}

object DisabledDeckTransport : DeckTransport {
    override val state: String = "Not paired — nothing leaves this phone"
    override fun offer(event: GuideMessageEvent) = Unit
}
