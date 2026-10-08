"""Process-lifetime exclusive playback admission shared by trusted audio owners."""
import fcntl,os
class AudioLease:
    def __init__(self,path='/run/guideos-audio/playback.lock'):self.path=path;self.fd=None
    def acquire(self):
        if self.fd is not None:return
        fd=os.open(self.path,os.O_RDWR|os.O_CREAT|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            os.close(fd);raise ValueError('Another player owns the audio output. Stop it first.') from None
        self.fd=fd
    def release(self):
        if self.fd is not None:os.close(self.fd);self.fd=None
