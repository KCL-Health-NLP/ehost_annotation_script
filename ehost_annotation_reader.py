# -*- coding: utf-8 -*-
"""
Created on Tue Aug  7 16:20:44 2018

@author: ABittar
"""

import os
import pandas as pd
import re
import sys
import xml.etree.ElementTree as ET

from xml.etree.ElementTree import ParseError


def get_corpus_files(main_dir, file_types='both'):
    """
    Get a list of all annotation files with the specified extensions
    stored under a base directory.
    """
    print('-- Listing files of type "' + file_types + '" in ' + main_dir)
    corpus_dirs = [os.path.join(main_dir, d) for d in os.listdir(main_dir) if os.path.isdir(os.path.join(main_dir, d))]
    
    corpus_list = []

    files = []
    for d in corpus_dirs:
        # TODO filter out non-directories (e.g when running on 'T:\\Andre Bittar\\ASD\\ASD_Tom\\')
        if file_types in ['txt', 'both']:
            files = [os.path.join(d, 'corpus', t) for t in os.listdir(os.path.join(d, 'corpus')) if os.path.splitext(t)[1] == '.txt' and os.path.isdir(os.path.join(d, 'corpus'))]
        if file_types in ['xml', 'both']:
            files += [os.path.join(d, 'saved', t) for t in os.listdir(os.path.join(d, 'saved')) if os.path.splitext(t)[1] == '.xml' and os.path.isdir(os.path.join(d, 'saved'))]
        corpus_list += files
        
    for file in corpus_list:
        assert os.path.isfile(file)

    return corpus_list


def load_mentions_with_attributes(pin, full_key=True):
    """
    Create a mapping of all mentions to all their associated attributes.
    This is necessary due to the structure of eHOST XML documents in which
    these entities are stored in separate XML tags.
    """
    
    xml = ET.parse(pin)
    annotation_nodes = xml.findall('annotation')
    attribute_nodes = xml.findall('.//stringSlotMention')
    mention_nodes = xml.findall('.//classMention')

    # Collect annotations and related data to insert into mentions
    annotations = {}
    for annotation_node in annotation_nodes:
        annotation_id = annotation_node.find('mention').attrib['id']
        annotator = annotation_node.find('annotator').text
        start = annotation_node.find('span').attrib['start']
        end = annotation_node.find('span').attrib['end']
        
        comment_node = annotation_node.find('annotationComment')
        comment = None
        if comment_node is not None:
            comment = comment_node.text
        
        annotations[annotation_id] = (annotator, start, end, comment)
    
    # Collect attributes and values to insert into mentions
    attributes = {}
    for attribute_node in attribute_nodes:
        attribute_id = attribute_node.attrib['id']
        attribute_name = attribute_node[0].attrib['id']
        attribute_value = attribute_node[1].attrib['value']
        attributes[attribute_id] = (attribute_name, attribute_value)
    
    # Collect mention classes so we can link them to the appropriate comment
    mentions = {}
    for mention_node in mention_nodes:
        mention_id = mention_node.attrib['id']
        mention_class_node = mention_node.findall('.//mentionClass')
        if len(mention_class_node) > 0:
            mention_class = mention_class_node[0].attrib['id']
            mention_text = mention_class_node[0].text
            annotator, start, end, comment = annotations.get(mention_id, None)
            mentions[mention_id] = { 'class': mention_class,
                                     'text' : mention_text,
                                     'annotator': annotator,
                                     'start': start,
                                     'end': end,
                                     'comment': comment
                                     }

        # Retrieve ids of attribute nodes
        slot_nodes = mention_node.findall('.//hasSlotMention')
        for slot_node in slot_nodes:
            temp = mentions.get(mention_id, None)
            if temp is not None:
                slot_id = slot_node.attrib['id']
                attr, val = attributes.get(slot_id)
                temp[attr] = val
                mentions[mention_id] = temp
    
    if full_key:
        key = pin
    else:
        key = os.path.basename(pin)
    
    return { key: mentions }


def convert_file_annotations(file_annotations):
    """
    Convert the multi-level dictionary format returned
    by load_mentions_with_attributes() into a flatter structure.
    """
    all_annotations = []
    for file_key in file_annotations:
        annotations = file_annotations[file_key]
        for annotation_id in annotations:
            annotation = annotations[annotation_id]
            all_annotations.append(annotation)
    return all_annotations


def count_mentions(pin, attribs=False):
    """
    Count all mention-level annotations in a document.
    """
    mention_counts = {}
    xml = None
    
    try:
        xml = ET.parse(pin)
    except ParseError as e:
        print('-- Error: unable to parse document ' + pin, file=sys.stderr)
        print(e, file=sys.stderr)
        return mention_counts
        
    if attribs:
        mention_nodes = xml.findall('.//stringSlotMention')
    else:
        mention_nodes = xml.findall('.//mentionClass')
        
    for mention_node in mention_nodes:
        if attribs:
            mention_class = mention_node[0].attrib['id']
        else:
            mention_class = mention_node.attrib['id']
        n = mention_counts.get(mention_class, 0) + 1
        mention_counts[mention_class] = n
    
    return mention_counts


def batch_count_mentions(pin, attribs=False):
    """
    Count total mentions in a directory.
    """
    files = os.listdir(pin)
    
    global_counts = {}
    
    for f in files:
        fin = os.path.join(pin, f)
        counts = count_mentions(fin, attribs=attribs)
        
        for key in counts:
            tmp = global_counts.get(key, 0) + 1
            global_counts[key] = tmp
    
    return global_counts


def batch_process_directory(pin, full_key=True):
    """
    Get all annotations from the corpus and store a mapping of file names to 
    annotations.
    """
    global_annotations = {}
    
    d_list = [os.path.join(pin, os.path.join(d, 'saved')) for d in os.listdir(pin) if not '.' in d]
    
    for d in d_list:
        f_list = [os.path.join(d,f) for f in os.listdir(d) if f.endswith('knowtator.xml')]
        
        for f in f_list:
            curr_annotations = load_mentions_with_attributes(f, full_key=full_key)
            global_annotations.update(curr_annotations)
            
    return global_annotations


def save_as_ehost_text(pin, pout_d):
    """
    Save texts from a Dataframe in eHOST directory structure.
    Directories are BRCIDs and file names are made up of the date and CN_Doc_ID of the documents.
    NB: make sure all column names are as required by the function.
    """
    gp = pd.read_pickle(pin).groupby('BrcId')
    
    for g in gp:
        for i, row in g[1].iterrows():
            brcid = str(row.BrcId)
            cndocid = str(row.CN_Doc_ID)
            text = row.text
            # skip empty documents
            if text is None:
                continue
            date = str(row.ViewDate.strftime('%Y-%m-%d'))
            dout = os.path.join(pout_d, brcid)
            corpus_dir = os.path.join(dout, 'corpus')
            
            if not os.path.isdir(dout):
                os.mkdir(dout)
                os.mkdir(os.path.join(dout, 'config'))
                os.mkdir(corpus_dir)
                os.mkdir(os.path.join(dout, 'saved'))
            
            fout = date + '_' + cndocid + '_00001.txt'
            pout = os.path.join(corpus_dir, fout)
            
            while os.path.isfile(pout):
                match = re.search('_([0-9]+).txt', pout)
                if match is not None:
                    fout = date + '_' + cndocid + '_' + str(int(match.group(1)) + 1).zfill(5) + '.txt'
                    pout = os.path.join(corpus_dir, fout)
            
            print('-- Writing file:', pout)
            with open(pout, 'w', encoding='utf-8') as output:
                output.write(text)
            output.close()
            
    print('Done.')


def ehost2tsv(pin, pout_d, annotation_types, verbose=False):
    """
    Save an eHOST annotated file in tabulation-separated values (TSV) format.
    pin: the input file path
    pout_d: the output directory path
    annotation_types: the list of all annotation types to output as columns
    word\tann1\tann2\t...\tann_n
    """

    # Set up spaCy
    import spacy
    from spacy.tokens import Token
    nlp = spacy.load('en_core_web_sm')    
    Token.set_extension('sentnum', default=False, force=True)

    # Create output directory and file path
    if not os.path.exists(pout_d):
        os.makedirs(pout_d)
    pout = os.path.join(pout_d, os.path.splitext(os.path.basename(pin))[0] + '.csv')
    
    # Avoid duplicates of obligatory default atttributes
    annotation_types = sorted(set(annotation_types).difference(set(['text', 'start', 'end'])))
    
    # Get annotations
    def annotations_by_start_offset(annotations):
        """
        Return annotations by start offset
        """
        ann_dict = {}
        for ann in annotations:
            start = int(ann['start'])
            ann_dict[start] = ann
    
        return ann_dict

    annotations = convert_file_annotations(load_mentions_with_attributes(pin))
    annotations = annotations_by_start_offset(annotations)

    # Get eHOST text
    pin_text = pin.replace('saved', 'corpus').replace('.knowtator.xml', '')
    assert os.path.isfile(pin_text)
    
    text = open(pin_text, 'r').read()
    doc = nlp(text)
    
    # Store sentence numbers on tokens
    for i, sent in enumerate(doc.sents):
        for token in sent:
            token._.sentnum = i
    
    flagged = []
    i = 0
    
    df = pd.DataFrame(columns=['sentnum', 'start', 'end', 'word', 'lemma', 'pos', 'dep', 'head'] + annotation_types)
    while i < len(doc):
        token = doc[i]
        token_start = token.idx
        token_end = token.idx + len(token) - 1
            
        output = []
        if token_start in annotations:
            ann = annotations[token_start]
            ann_text = ann.get('text')
            ann_doc = nlp(ann_text)
            for ann_tok in ann_doc:
                ann_output = []
                ann_tok_start = token_start + ann_tok.idx
                ann_tok_end = ann_tok_start + len(ann_tok) - 1
                output_str = str(token._.sentnum) + '\t' + str(ann_tok_start) + '\t' + str(ann_tok_end) + '\t' + ann_tok.text + '\t' + ann_tok.lemma_ + '\t' + token.tag_ +  '\t' + ann_tok.dep_ + '\t' + str(ann_tok.head)
                ann_output += [token._.sentnum, ann_tok_start, ann_tok_end, ann_tok.text, ann_tok.lemma_, token.tag_ , ann_tok.dep_, ann_tok.head]
                if verbose:
                    print(output_str, end='\t', file=sys.stdout)
                for ann_type in annotation_types:
                    if verbose:
                        print(ann.get(ann_type, '-') + '\t', end='\t', file=sys.stdout)
                    ann_output.append(ann.get(ann_type, '-'))
                df.loc[i] = ann_output
                if verbose:
                    print('\n', end='', file=sys.stdout)
            flagged.append(token_start)
            i += len(ann_doc) - 1
        else:
            output_str = str(token._.sentnum) + '\t' + str(token_start) + '\t' + str(token_end) + '\t' + token.text + '\t' + token.lemma_ + '\t' + token.tag_ + '\t' + token.dep_ + '\t' + str(token.head)
            output_str += '\t-' * len(annotation_types)
            output += [token._.sentnum, token_start, token_end, token.text, token.lemma_, token.tag_, token.dep_, token.head]
            output += ['-'] * len(annotation_types)
            if verbose:
                print(output_str, end='', file=sys.stdout)
            # Store the line in the DataFrame
            df.loc[i] = output
        if verbose:
            print('', file=sys.stdout)
        i += 1
    
    # Check the annotation offsets are equivalent
    gold = sorted(annotations.keys())
    flagged = sorted(flagged)
    #print(gold, len(gold))
    #print(flagged, len(flagged))
    if flagged != gold:
        print('-- Unequal number of annotations for', pin)

    df.to_csv(pout)
    print('-- Wrote file:', pout)
    
    return df