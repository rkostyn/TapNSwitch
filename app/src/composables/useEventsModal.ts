// Open state of the Events modal, shared so that anything (the header's
// buttons, or App when an event match is finished) can open it on an event.

import { readonly, ref } from 'vue'

const showEvents = ref(false)
/** Event to open straight into its detail view; null opens the list. */
const eventsInitialId = ref<string | null>(null)

function openEvents(eventId: string | null = null) {
  eventsInitialId.value = eventId
  showEvents.value = true
}

function closeEvents() {
  showEvents.value = false
}

export function useEventsModal() {
  return {
    showEvents: readonly(showEvents),
    eventsInitialId: readonly(eventsInitialId),
    openEvents,
    closeEvents,
  }
}
