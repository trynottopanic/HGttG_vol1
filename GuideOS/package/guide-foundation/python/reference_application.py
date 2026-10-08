"""Harmless runtime conformance application. Uses no owner documents."""
import time

def application(api):
    private=api.acquire(2);visual=api.acquire(3);actions=api.acquire(4);text=api.acquire(5)
    draft=api.read(private,'checkpoint')
    api.present(visual,'Application host test',draft or 'Ready. No external documents are accessed.',['Enter test text'])
    api.ready()
    while True:
        event=api.event()
        if event[0]==1:api.text(text,draft,128)
        elif event[0]==2 and event[1] is not None:
            draft=event[1];api.present(visual,'Application host test',draft,['Enter test text'])
        elif event[0]==3:
            receipt=api.write(private,'checkpoint',draft);api.checkpointed(receipt)
        time.sleep(.02)
