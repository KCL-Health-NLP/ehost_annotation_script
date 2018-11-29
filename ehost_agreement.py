# -*- coding: utf-8 -*-
"""
Created on Tue Jul 24 15:46:43 2018

@author: ABittar
"""

import os
import sys

from ehost_annotation_reader import load_mentions_with_attributes, convert_file_annotations, get_corpus_files, count_mentions
from collections import Counter
from sklearn.metrics import cohen_kappa_score, precision_recall_fscore_support


# specifies the attributes to evaluate
ATTRS = set([])
IGNORE_ATTRS = ['start', 'end', 'class', 'annotator', 'comment', 'text']


def get_all_annotated_attributes(files1, files2):
    """
    Update the set of attributes to evaluate.
    """
    global ATTRS
    global IGNORE_ATTRS
    
    for f in files1:
        d = convert_file_annotations(load_mentions_with_attributes(f))
        flat_list = [item for sublist in d for item in sublist if item not in IGNORE_ATTRS]
        ATTRS = ATTRS.union(set(flat_list))
    
    for f in files2:
        d = convert_file_annotations(load_mentions_with_attributes(f))
        flat_list = [item for sublist in d for item in sublist if item not in IGNORE_ATTRS]
        ATTRS = ATTRS.union(set(flat_list))


def match_span(a1, a2, matching):
    s1 = int(a1['start'])
    s2 = int(a2['start'])
    e1 = int(a1['end'])
    e2 = int(a2['end'])
    t1 = a1['text']
    t2 = a2['text']

#    match_str = '{} {} {}\n        {} {} {}'.format(s1, e1, t1, s2, e2, t2)
    match_str = '{} {} {}\n{} {} {}'.format(s1, e1, t1, s2, e2, t2)
    
    # Exact match (strict matching)
    if s1 == s2 and e1 == e2:
#        match_str = 'match 1 ' + match_str
        return True, match_str
       
    if matching == 'relaxed':
        # s1_[ s2_< > ] (s1 INCLUDES s2)
        if s1 <= s2 and e1 >= e2:
            #match_str = 'match 2 ' + match_str
            return True, match_str

        # s2_< s1_[] > (s2 INCLUDES s1)
        if s1 >= s2 and e1 <= e2:
            #match_str = 'match 3 ' + match_str
            return True, match_str
    
        # s1_[ s2_<] > (s1 OVERLAP_BEFORE s2)
        if s1 <= s2 and e1 >= s2:
            #match_str = 'match 4 ' + match_str
            return True, match_str
        
        # s2_< s1_[> ] (s1 OVERLAP_AFTER s2)
        if s1 >= s2 and s1 <= e2:
            #match_str = 'match 5 ' + match_str
            return True, match_str
    
    #print('no', match_str)
    return False, ''


def match_attributes(tag1, tag2):
    attr_agr = {}
    
    attrs_to_check = [a for a in tag1.keys() if a not in ['start', 'end', 'text', 'comment', 'annotator']]
    
    #for a in attrs_to_check:
    #    attr_agr[a] = {'tp': 0, 'tn': 0, 'fp': 0, 'fn': 0}
    
    match_str = ''
    
    for attr in attrs_to_check:
        val1 = tag1.get(attr, None)
        val2 = tag2.get(attr, None)
        if val1 is not None and val2 is not None:
            if val1 == val2:
                scores = attr_agr.get(attr, {})
                tp = scores.get('tp', 0) + 1
                scores['tp'] = tp
                attr_agr[attr] = scores
            else:
                # this is fp and fn - weird
                scores = attr_agr.get(attr, {})
                fp = scores.get('fp', 0) + 1
                scores['fp'] = fp
                attr_agr[attr] = scores
                fn = scores.get('fn', 0) + 1
                scores['fn'] = fn
                attr_agr[attr] = scores
                match_str += '-- attribute disagreement on ' + attr + ': ' + str(val1) + ' vs. ' + str(val2) + '\n'
        elif val1 is None and val2 is not None:
            scores = attr_agr.get(attr, {})
            fp = scores.get('fp', 0) + 1
            scores['fp'] = fp
            attr_agr[attr] = scores
            match_str += '-- attribute disagreement on ' + attr + ': ' + str(val1) + ' vs. ' + str(val2) + '\n'
        elif val1 is not None and val2 is None:
            scores = attr_agr.get(attr, {})
            fn = scores.get('fn', 0) + 1
            scores['fn'] = fn
            attr_agr[attr] = scores
            match_str += '-- attribute disagreement on ' + attr + ': ' + str(val1) + ' vs. ' + str(val2) + '\n'
        else:
            scores = attr_agr.get(attr, {})
            tn = scores.get('tn', 0) + 1
            scores['tn'] = tn
            attr_agr[attr] = scores
            match_str += '-- attribute disagreement on ' + attr + ': ' + str(val1) + ' vs. ' + str(val2) + '\n'

    return attr_agr, match_str


def get_tag_attrs(tag):
    global ATTRS
    values = {}
    
    for attr in ATTRS:
        val = tag.get(attr, None)
        values[attr] = val
    
    return values


def count_agreements(pin1, pin2, report_string, matching):
    ann1 = load_mentions_with_attributes(pin1)
    ann2 = load_mentions_with_attributes(pin2)
    
    tags1 = convert_file_annotations(ann1)
    tags2 = convert_file_annotations(ann2)
    
    matched = []
    
    tp = fp = fn = 0
    
    attr_agr = {}
    attr_vals1 = []
    attr_vals2 = []
    
    report_string += '--------------------\n'
    report_string += 'MATCHING ANNOTATIONS\n'
    report_string += '--------------------\n'
    
    for tag1 in tags1:
        for tag2 in tags2:
            m, r = match_span(tag1, tag2, matching)
            if m:
                report_string += r + '\n'
                # span
                matched.append(tag1)
                matched.append(tag2)
                tp += 1
                # attributes
                a, r = match_attributes(tag1, tag2)
                report_string += r
                for attr in a:
                    curr_agr = attr_agr.get(attr, {})
                    new_agr = a[attr]
                    c = dict(Counter(curr_agr) + Counter(new_agr))
                    attr_agr[attr] = c
                # testing
                vals1 = get_tag_attrs(tag1)
                vals2 = get_tag_attrs(tag2)
                attr_vals1.append(vals1)
                attr_vals2.append(vals2)
                break

    for tag2 in tags2:
        if tag2 not in matched:
            for tag1 in tags1:
                if tag1 not in matched:
                    m, r = match_span(tag2, tag1, matching)
                    if m:
                        report_string += r + '\n'
                        # span
                        matched.append(tag1)
                        matched.append(tag2)
                        tp += 1
                        # attributes
                        a, r = match_attributes(tag1, tag2)
                        report_string += r
                        for attr in a:
                            curr_agr = attr_agr.get(attr, {})
                            new_agr = a[attr]
                            c = dict(Counter(curr_agr) + Counter(new_agr))
                            attr_agr[attr] = c
                        # testing
                        vals1 = get_tag_attrs(tag1)
                        vals2 = get_tag_attrs(tag2)
                        attr_vals1.append(vals1)
                        attr_vals2.append(vals2)
                        break

    report_string += '-------------------\n'
    report_string += 'MISSING ANNOTATIONS\n'
    report_string += '-------------------\n'
    for tag1 in tags1:
        if tag1 not in matched:
            report_string += str(tag1['start']) + ' ' + str(tag1['end']) + ' ' + str(tag1['text']) + '\n'
            fn += 1

    report_string += '--------------------\n'
    report_string += 'SPURIOUS ANNOTATIONS\n'
    report_string += '--------------------\n'
    for tag2 in tags2:
        if tag2 not in matched:
            report_string += str(tag2['start']) + ' ' + str(tag2['end']) + ' ' + str(tag2['text']) + '\n'
            fp += 1
    
    report_string += '==========\n'

    return tp, fp, fn, attr_agr, attr_vals1, attr_vals2, report_string


def attr_prf(attr_agr_g, report_string):
    """
    Hand-coded calculations
    """
    # Using my metric - gives the same results as scikit-learn
    for attr in attr_agr_g:
        report_string += '-- ' + attr + '\n'
        tp = attr_agr_g[attr].get('tp', 0.0)
        fp = attr_agr_g[attr].get('fp', 0.0)
        #tn = attr_agr_g[attr].get('tn', 0.0)
        fn = attr_agr_g[attr].get('fn', 0.0)
        p, r, f = prf(tp, fp, fn)
        report_string += '\tprecision: ' + str(p) + '\n'
        report_string += '\trecall   : ' + str(r) + '\n'
        report_string += '\tf-score  : ' + str(f) + '\n'

    return report_string


def prf(tp, fp, fn):
    print('-- Calculating precision, recall and f-score')
    print('   tp:', tp)
    print('   fp:', fp)
    print('   fn:', fn)

    if tp + fp == 0.0 or tp + fn == 0.0:
        print('-- Warning: cannot calculate metrics with zero denominator')
        return 0.0, 0.0, 0.0

    p = tp / (tp + fp)
    r = tp / (tp + fn)
    f = 2 * p * r / (p + r)
    
    return p, r, f


def batch_agreement(ann_dir1, ann_dir2, report_dir=None, matching='relaxed', compare_attributes=True, ignore_attributes=[]):
    """
    ann_dir_1 and ann_dir_2 are tuples of the form:
        ('Annotator1_Name','Dir_1')
        ('Annotator2_Name','Dir_2')
    report_dir: specifies the output directory for the report file (overwrite existing report for the specified annotator pair)
    matching: specifies whether spans must be strict matches (strict) or partial matches (relaxed)
    compare_attributes: calculate agreement for span attributes (True/False)
    ignore_attributes: list of attributes to ignore
    """
    global ATTRS
    
    if matching not in ['strict', 'relaxed']:
        raise ValueError('-- Invalid matching type "' + str(matching) + '". Use "strict" or "relaxed".')
    
    if report_dir is not None and not os.path.isdir(report_dir):
        raise ValueError('-- Invalid report directory "' + str(matching) + '".')
    
    ann1 = ann_dir1[0]
    dir1 = ann_dir1[1]
    
    ann2 = ann_dir2[0]
    dir2 = ann_dir2[1]
    
    files1 = [f for f in get_corpus_files(dir1) if f.endswith('xml')]
    files2 = [f for f in get_corpus_files(dir2) if f.endswith('xml')]
    
    # Get all annotated attributes - need to do this here
    get_all_annotated_attributes(files1, files2)
    
    #print(files1)
    #print('---')
    #print(files2)
    
    if report_dir is not None:
        pout = os.path.join(report_dir, 'agreement_report_' + ann1 + '_' + ann2 + '.txt')
        fout = open(pout, 'w')
    
    report_string =  '================================\n'
    report_string += 'INTER-ANNOTATOR AGREEMENT REPORT\n'
    report_string += '================================\n'

    report_string += 'Input1 (' + ann1 + '): ' + dir1 + '\n'
    report_string += 'Input2 (' + ann2 + '): ' + dir2 + '\n'
    report_string += 'Matching: ' + matching + '\n'
    report_string += '-------------------------\n'

    tp_g = fp_g = fn_g = 0.0
    
    attr_agr_g = {}
    attr_vals1_g = []
    attr_vals2_g = []
    
    for f1 in files1:
        for f2 in files2:
            # Only compare files that are in both sets
            f1b = os.path.basename(f1)
            f2b = os.path.basename(f2)
            if f1b == f2b:
                report_string += 'File1: ' + f1 + '\n'
                report_string += 'File2: ' + f2 + '\n'
                tp, fp, fn, attr_agr, attr_vals1, attr_vals2, report_string = count_agreements(f1, f2, report_string, matching)
                tp_g += tp
                fp_g += fp
                fn_g += fn
                for attr in attr_agr:
                    curr_agr = attr_agr_g.get(attr, {})
                    new_agr = attr_agr[attr]
                    c = dict(Counter(curr_agr) + Counter(new_agr))
                    attr_agr_g[attr] = c
                
                # Used for scikit-learn calculations
                attr_vals1_g.extend(attr_vals1)
                attr_vals2_g.extend(attr_vals2)

    assert len(attr_vals1_g) == len(attr_vals2_g)
    
    report_string += '\n'
    report_string += 'SPANS\n'
    report_string += '-----\n'

    p, r, f = prf(tp_g, fp_g, fn_g)

    report_string += 'precision: ' + str(p) + '\n'
    report_string += 'recall   : ' + str(r) + '\n'
    report_string += 'f-score  : ' + str(f) + '\n'

    # Using scikit-learn (per-class results)
    if compare_attributes:
        report_string += '\n'
        report_string += 'ATTRIBUTES\n'
        report_string += '----------\n'
        
        if len(ATTRS) == 0:
            report_string += '-- No attributes to compare\n'
        
        for attr in sorted(ATTRS):
            report_string += '-- ' + attr + '\n'
            sample1 = [k.get(attr, None) for k in attr_vals1_g]
            sample2 = [k.get(attr, None) for k in attr_vals2_g]
        
            scores = {}
            scores['macro'] = precision_recall_fscore_support(sample1, sample2, average='macro')
            scores['micro'] = precision_recall_fscore_support(sample1, sample2, average='micro')

            for score in scores:
                report_string += '\tprecision (' + score + '): ' + str(scores[score][0]) + '\n'
                report_string += '\trecall    (' + score + '): ' + str(scores[score][1]) + '\n'
                report_string += '\tf-score   (' + score + '): ' + str(scores[score][2]) + '\n'

            k = cohen_kappa_score(sample1, sample2)
            report_string += '\tkappa            : ' + str(k) + '\n'

    #report_string = attr_prf(attr_agr_g, report_string)

    print(report_string)

    if report_dir is not None:
        print('-- Printed report to file:', pout, file=sys.stderr)
        fout.write(report_string)
        fout.close()