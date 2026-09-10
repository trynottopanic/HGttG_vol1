package org.thirdway.guideos.companion.events

class BoundedEventQueue(private val capacity: Int = 50) {
    private val events = ArrayDeque<GuideMessageEvent>()
    private val knownIds = HashSet<String>()

    @Synchronized
    fun offer(event: GuideMessageEvent, nowMillis: Long = System.currentTimeMillis()): Boolean {
        discardExpired(nowMillis)
        if (event.expiresAtMillis <= nowMillis || !knownIds.add(event.eventId)) return false
        while (events.size >= capacity) {
            knownIds.remove(events.removeFirst().eventId)
        }
        events.addLast(event)
        return true
    }

    @Synchronized
    fun snapshot(nowMillis: Long = System.currentTimeMillis()): List<GuideMessageEvent> {
        discardExpired(nowMillis)
        return events.toList()
    }

    @Synchronized
    fun clear() {
        events.clear()
        knownIds.clear()
    }

    private fun discardExpired(nowMillis: Long) {
        while (events.firstOrNull()?.expiresAtMillis?.let { it <= nowMillis } == true) {
            knownIds.remove(events.removeFirst().eventId)
        }
    }
}
