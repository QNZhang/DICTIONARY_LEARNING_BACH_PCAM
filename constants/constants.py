# -*- coding: utf-8 -*-
""" constants """

from collections import namedtuple
from core.exceptions.dataset import LabelIdInvalid


LabelItem = namedtuple('LabelItem', ['id', 'name'])


class Label:
    """ Holds labels and basic handlers """
    NORMAL = LabelItem(0, "Normal")
    BENIGN = LabelItem(1, "Benign")
    INSITU = LabelItem(2, "In Situ")
    INVASIVE = LabelItem(3, "Invasive")

    CHOICES = (NORMAL, BENIGN, INSITU, INVASIVE)
    INDEX = dict(CHOICES)

    @classmethod
    def is_valid_option(cls, id_):
        """ Returns true if the id_ belongs to any of the choices """
        return id_ in cls.INDEX.keys()

    @classmethod
    def get_name(cls, id_):
        """ Returns the name associated with the provided label id """
        if not cls.is_valid_option(id_):
            raise LabelIdInvalid()

        return cls.INDEX[id_]

    @classmethod
    def get_choices_as_string(cls):
        """ Returns labels information """
        return ', '.join(tuple('{} : {}'.format(*item) for item in cls.CHOICES))