package org.thirdway.guideos.companion.events

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BoundedEventQueueTest {
    @Test
    fun rejectsDuplicatesAndExpiredEvents() {
        val queue = BoundedEventQueue(2)
        val event = event("one", expiresAt = 200)

        assertTrue(queue.offer(event, nowMillis = 100))
        assertFalse(queue.offer(event, nowMillis = 100))
        assertFalse(queue.offer(event("old", expiresAt = 99), nowMillis = 100))
        assertEquals(listOf("one"), queue.snapshot(100).map { it.eventId })
    }

    @Test
    fun dropsOldestEventAtCapacity() {
        val queue = BoundedEventQueue(2)
        queue.offer(event("one"), 100)
        queue.offer(event("two"), 100)
        queue.offer(event("three"), 100)

        assertEquals(listOf("two", "three"), queue.snapshot(100).map { it.eventId })
    }

    private fun event(id: String, expiresAt: Long = 1_000) = GuideMessageEvent(
        eventId = id,
        occurredAtMillis = 1,
        expiresAtMillis = expiresAt,
        sender = "Person",
        conversation = null,
        preview = null,
        contentState = "hidden",
    )
}
