from shamela_books import RateLimiter


class FakeClock:
    def __init__(self):
        self.t = 0.0
    def time(self):
        return self.t
    def sleep(self, dt):
        self.t += dt


def test_rate_limiter_zero_jitter_spacing():
    clk = FakeClock()
    rl = RateLimiter(0.5, jitter=0.0, time_fn=clk.time, sleep_fn=clk.sleep)
    times = []
    for _ in range(4):
        rl.wait()
        times.append(clk.time())
    # Expect steps of exactly 0.5
    diffs = [round(times[i]-times[i-1], 3) for i in range(1, len(times))]
    assert diffs == [0.5, 0.5, 0.5]
