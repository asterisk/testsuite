"""
tonetest - analyze monophonic tones in wav file

Copyright (c) 2016, Digium, Inc
Scott Griepentrog <sgriepentrog@digium.com>
"""

import numpy
import wave


class Analyzer(object):
    def __init__(self, samples_per_second, full_scale):
        self.samples_per_second = samples_per_second
        self.full_scale = full_scale
        self.samples = 0
        self.last_sample = 0
        self.results = []
        self.last_positive = 0
        self.last_quiet = 0
        self.peak = 0
        self.result_current = None
        # controls affecting results accuracy
        self.tolerance_amplitude = 0.1
        self.tolerance_seconds = 0.05

    def store_results(self, frequency, lo, hi, amplitude):
        second = float(self.samples) / float(self.samples_per_second)
        if self.result_current:
            old_freq = self.result_current['frequency']
            frequency_changed = old_freq < lo or old_freq > hi
            elapsed = second - self.result_current['seconds']
            if frequency_changed:
                if elapsed < self.tolerance_seconds:
                    # ignore short duration glitch in freq detection
                    self.result_current['frequency'] = frequency
                    self.result_current['amplitude'] = amplitude
                else:
                    self.results.append(self.result_current)
                    self.result_current = None

        if not self.result_current:
            self.result_current = {
                'frequency': frequency,
                'amplitude': amplitude,
                'seconds': second
            }

    def process_each(self, sample):
        if sample > self.peak:
            self.peak = sample
        if self.last_sample <= 0 and sample > 0 and self.samples:
            amplitude = float(self.peak) / float(self.full_scale)
            count = self.samples - self.last_positive
            frequency = float(self.samples_per_second) / float(count)
            freq_hi = float(self.samples_per_second) / float(count - 1)
            freq_lo = float(self.samples_per_second) / float(count + 1)
            if amplitude < self.tolerance_amplitude:
                frequency = 0
                freq_hi = 0
                freq_lo = 0
                amplitude = 0
            if self.last_positive:
                self.store_results(frequency, freq_lo, freq_hi, amplitude)
            self.peak = 0
            self.last_positive = self.samples
            self.last_quiet = self.samples
        self.last_sample = sample
        self.samples += 1
        elapsed_samples = self.samples - self.last_quiet
        elapsed_seconds = float(elapsed_samples) / float(self.samples_per_second)
        if elapsed_seconds > self.tolerance_seconds:
            self.store_results(0.0, 0.0, 0.0, 0.0)
            self.last_quiet = self.samples
            self.last_positive = 0

    def process(self, samples):
        for sample in samples:
            self.process_each(sample)

    def get_results(self):
        if self.result_current:
            self.results.append(self.result_current)
        last = None
        for result in self.results:
            if last:
                last['duration'] = result['seconds'] - last['seconds']
            last = result
        second = float(self.samples) / float(self.samples_per_second)
        last['duration'] = second - last['seconds']
        return self.results


def tonetest(filename):
    wavefile = wave.open(filename, 'rb')

    if wavefile.getnchannels() != 1:
        raise Exception('Unexpected channels')

    bytes_per_sample = wavefile.getsampwidth()

    if bytes_per_sample == 1:  # this might be uLaw?
        sample_type = numpy.int8
        full_scale = 127
    elif bytes_per_sample == 2:
        sample_type = numpy.int16
        full_scale = 32767
    else:
        raise Exception('Unexpected sample width')

    samples_per_second = wavefile.getframerate()

    chunk_size = samples_per_second

    analyzer = Analyzer(samples_per_second, full_scale)

    while True:
        data = wavefile.readframes(chunk_size)
        if not data:
            break

        samples = numpy.fromstring(data, dtype=sample_type)

        analyzer.process(samples)

    wavefile.close()

    return analyzer.get_results()
