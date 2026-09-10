package org.thirdway.guideos.companion.events

import org.thirdway.guideos.companion.transport.DeckTransport
import org.thirdway.guideos.companion.transport.DisabledDeckTransport

object EventPipeline {
    val queue = BoundedEventQueue(50)

    // Delivery stays closed until authenticated Deck pairing is implemented.
    @Volatile
    var transport: DeckTransport = DisabledDeckTransport

    fun accept(event: GuideMessageEvent) {
        if (!queue.offer(event)) return
        transport.offer(event)
    }
}
