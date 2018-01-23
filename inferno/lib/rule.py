import sys

from disco.worker.classic.worker import Params
from disco.core import result_iterator
from disco.func import chain_stream
from disco.func import disco_output_stream
from disco.func import gzip_stream
from disco.func import map_output_stream
from disco.func import reduce_output_stream

from inferno.lib.disco_ext import sorted_iterator, json_output_stream
from inferno.lib.map import keyset_map
from inferno.lib.reader import csv_reader
from inferno.lib.reader import json_reader
from inferno.lib.reduce import keyset_reduce
from inferno.lib.result import keyset_result


gzip_csv_stream = gzip_stream + (csv_reader,)
gzip_json_stream = gzip_stream + (json_reader,)
chunk_json_stream = chain_stream + (json_reader,)
chunk_csv_stream = chain_stream + (csv_reader,)
json_reduce_output_stream = (reduce_output_stream, json_output_stream)


def crc_partition(key, nr_partitions, params):
    import binascii
    return binascii.crc32(key) % nr_partitions


class Keyset(object):

    def __init__(self,
                 key_parts=None,
                 value_parts=None,
                 column_mappings=None,
                 table=None,
                 parts_preprocess=None,
                 parts_postprocess=None,
                 **kwargs):

        self.key_parts = ['_keyset'] + list(key_parts or [])
        self.value_parts = value_parts or []
        self.column_mappings = column_mappings or []
        self.table = table
        self.parts_preprocess = parts_preprocess or []
        self.parts_postprocess = parts_postprocess or []
        self.kwargs = kwargs

    def as_dict(self):
        rval = {
            'key_parts': self.key_parts,
            'value_parts': self.value_parts,
            'column_mappings': self.column_mappings,
            'table': self.table,
            'parts_preprocess': self.parts_preprocess,
            'parts_postprocess': self.parts_postprocess}
        rval.update(self.kwargs)
        return rval


class InfernoRule(object):

    def __init__(self,
                 # name, on/off
                 name='_unnamed_',
                 run=True,

                 # throttle
                 min_blobs=1,
                 max_blobs=sys.maxint,
                 partitions=200,
                 partition_function=crc_partition,
                 scheduler=None,
                 worker=None,
                 time_delta=None,
                 newest_first=True,

                 # archive
                 archive=False,
                 archive_tag_prefix='processed',

                 # nuke
                 nuke=False,

                 # map
                 map_init_function=lambda x, y: x,
                 map_function=keyset_map,
                 map_input_stream=chunk_csv_stream,
                 map_output_stream=(map_output_stream, disco_output_stream),

                 #combine
                 combiner_function=None,

                 # reduce
                 reduce_function=keyset_reduce,
                 reduce_output_stream=(reduce_output_stream, disco_output_stream),

                 # result
                 # result_iterator_override -->
                 #   see inferno.lib.disco_ext.sorted_iterator for signature
                 result_iterator_override=None,
                 result_processor=keyset_result,
                 result_tag=None,
                 result_tag_suffix=True,
                 save=False,
                 sort=True,
                 sort_buffer_size='10%',
                 sorted_results=True,

                 # keysets
                 keysets=None,
                 key_parts=None,
                 value_parts=None,
                 column_mappings=None,
                 table=None,
                 keyset_parts_preprocess=None,
                 parts_postprocess=None,

                 # input
                 day_range=0,
                 day_offset=0,
                 day_start=None,
                 source_tags=None,
                 source_urls=None,

                 # other
                 rule_init_function=None,
                 rule_cleanup=None,
                 parts_preprocess=None,
                 field_transforms=None,
                 required_files=None,
                 required_modules=None,
                 retry=False,
                 retry_limit=2,
                 retry_delay=1,

                 # notifications --> notify_addresses must be list of addresses
                 notify_on_fail=False,
                 notify_on_success=False,
                 notify_addresses=None,
                 **kwargs):

        self.qualified_name = name
        if kwargs:
            self.params = Params(**kwargs)
        else:
            self.params = Params()

        if not scheduler:
            scheduler = {'force_local': False, 'max_cores': 200}

        # name, on/off
        self.run = run
        self.name = name

        # throttle
        self.min_blobs = min_blobs
        self.max_blobs = max_blobs
        self.partitions = partitions
        self.partition_function = partition_function
        self.scheduler = scheduler
        self.time_delta = time_delta
        if self.time_delta is None:
            self.time_delta = {'minutes': 5}
        self.newest_first = newest_first
        self.worker = worker

        # archive
        self.archive = archive
        self.archive_tag_prefix = archive_tag_prefix

        # nuke
        self.nuke = nuke

        # map
        self.map_init_function = map_init_function
        self.map_function = map_function
        self.map_input_stream = map_input_stream
        self.map_output_stream = map_output_stream
        self.combiner_function = combiner_function

        # reduce
        self.reduce_function = reduce_function
        self.reduce_output_stream = reduce_output_stream

        # result
        self.result_processor = result_processor
        self.result_tag = result_tag
        self.result_tag_suffix = result_tag_suffix
        self.save = save
        self.sort = sort
        self.sort_buffer_size = sort_buffer_size
        if result_iterator_override:
            self.result_iterator = result_iterator_override
        elif self.sort and sorted_results:
            self.result_iterator = sorted_iterator
        else:
            self.result_iterator = result_iterator

        # input
        if isinstance(source_tags, basestring):
            source_tags = [source_tags]
        self.day_range = day_range
        self.day_offset = day_offset
        self.day_start = day_start
        self.source_tags = source_tags or []

        # keysets
        keyset_dict = {}
        if keysets:
            for keyset_name, keyset_obj in keysets.items():
                keyset_dict[keyset_name] = keyset_obj.as_dict()
        else:
            keyset_dict['_default'] = Keyset(
                key_parts,
                value_parts,
                column_mappings,
                table,
                keyset_parts_preprocess,
                parts_postprocess).as_dict()
        self.params.keysets = keyset_dict

        self.params.parts_preprocess = parts_preprocess or []
        self.params.field_transforms = field_transforms or dict()

        # other
        self.rule_init_function = rule_init_function
        self.rule_cleanup = rule_cleanup
        self.retry = retry
        self.retry_limit = retry_limit
        self.retry_delay = retry_delay
        self.required_modules = required_modules or []
        self.required_files = required_files or []
        self.notify_on_fail = notify_on_fail
        self.notify_on_success = notify_on_success
        self.notify_addresses = notify_addresses or []
        self.source_urls = source_urls

    def __str__(self):
        return '<InfernoRule: %s>' % self.name

    @property
    def is_atomic(self):
        return self.archive

    def summary_dict(self):
        def fstr(func):
            return "%s.%s" % (func.__module__, func.__name__)

        def fname(funcvec):
            # serialize collections of funcs as collections of func names
            return [fstr(func) for func in funcvec] if funcvec else []

        # mostly just a dump of the __dict__, some exceptions
        return dict(
            name=self.name,
            run=self.run,
            archive=self.archive,
            nuke=self.nuke,
            map_input_stream=fname(self.map_input_stream),
            map_function=fstr(self.map_function),
            reduce_function=fstr(self.reduce_function),
            keysets=self.params.keysets,
            parts_preprocess=fname(self.params.parts_preprocess))


def extract_subrules(rule):
    for item in rule.source_tags:
        if isinstance(item, InfernoRule):
            yield item


def flatten_rules(rule):
    rules = []
    if not isinstance(rule, InfernoRule):
        return rules
    else:
        for item in rule.source_tags:
            rules += flatten_rules(item)
        # append the top-level rule to the end of list
        rules.append(rule)

    return rules


def deduplicate_rules(rules):
    dedup_rules = []
    for rule in rules:
        if not rule in dedup_rules:
            dedup_rules.append(rule)
    return dedup_rules
