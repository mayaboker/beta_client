from beta_client.timesync import TimeSyncEstimator


def test_matching_replies_mature_and_expire():
    estimator = TimeSyncEstimator()
    for index in range(5):
        sent = 2_000_000_000 + index * 200_000_000
        assert estimator.request(sent) == sent
        status = estimator.reply(sent - 1_000_000_000, sent, sent + 10_000_000)
        assert status.accepted_samples == index + 1
        assert status.fresh(status.updated_at) == (index == 4)
    assert status.rtt_ns == 10_000_000
    assert status.offset_ns == 1_005_000_000
    assert status.fresh(status.updated_at + 1.0)
    assert not status.fresh(status.updated_at + 1.001)


def test_wrong_echo_and_slow_reply_are_ignored():
    estimator = TimeSyncEstimator()
    sent = estimator.request(2_000_000_000)
    assert estimator.reply(1_000_000_000, sent - 1, sent + 1_000_000) is None
    assert estimator.reply(1_000_000_000, sent, sent + 40_000_001) is None
    assert estimator.reply(1_000_000_000, sent, sent + 10_000_000).accepted_samples == 1
    assert estimator.reply(1_000_000_000, sent, sent + 11_000_000) is None


def test_vehicle_clock_reset_invalidates_prior_samples():
    estimator = TimeSyncEstimator()
    for index in range(5):
        sent = 2_000_000_000 + index * 200_000_000
        estimator.request(sent)
        status = estimator.reply(1_000_000_000 + index * 200_000_000,
                                 sent, sent + 5_000_000)
    assert status.fresh(status.updated_at)
    sent = 3_000_000_000
    estimator.request(sent)
    reset = estimator.reply(100_000_000, sent, sent + 5_000_000)
    assert reset.accepted_samples == 1
    assert not reset.fresh(reset.updated_at)
