'''Common fixtures and functions for test files'''

import pytest
import random
import string

def jitter(mean):
    '''Make a number jitter a bit'''
    return int(max(1, random.normalvariate(mean, max(1, mean / 2))))

def random_word(mean_length=5):
    return ''.join(
        random.sample(string.ascii_letters, jitter(mean_length)))

def random_sentence(mean_length=10):
    return (' '.join(
        random_word() for _ in xrange(jitter(mean_length))) + '.'
    ).capitalize()

def random_paragraph(mean_length=4):
    return ' '.join(
        random_sentence() for _ in xrange(jitter(mean_length)))

def random_paragraphs(mean_length=5):
    return '\n\t'.join(
        random_paragraph() for _ in xrange(jitter(mean_length)))
