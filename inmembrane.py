#!/usr/bin/env python
# Copyright (c) 2012, Bosco Ho <boscoh@gmail.com>
# Copyright (c) 2012, Andrew Perry <ajperry@pansapiens.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following 
# conditions are met:

# 1. Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the 
# documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS 
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT 
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS 
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE 
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, 
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, 
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS 
# OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED 
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF 
# THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH 
# DAMAGE.


import sys
import os
import glob
import shutil
from optparse import OptionParser


from helpers import *


description = """
Inmembrane is a proteome annotation pipeline. It takes 
a FASTA file, then carries out sequential analysis of 
each sequence with a bunch of third-party programs, and 
collates the results.

(c) 2011 Bosco Ho and Andrew Perry
"""


# figure out absoulte directory for inmembrane scripts
module_dir = os.path.abspath(os.path.dirname(__file__))


# Load all modules found in plugins dynamically 
# Each module should have the structure where there is only 
# one main function with the same name of the function
# and takes two parameters:
#   mymodule.mymodule(params, proteins)
file_tag = os.path.join(module_dir, 'plugins', '*.py')
for plugin in glob.glob(file_tag):
  if "__init__" in plugin:
    continue
  plugin_name = os.path.basename(plugin)[:-3]
  exec('from plugins.%s import * ' % plugin_name)


default_params_str = """{
  'fasta': '',
  'csv': '',
  'output': '',
  'out_dir': '',
  'protocol': 'gram_neg', # 'gram_pos'
  'signalp4_organism': 'gram+',
  'signalp4_bin': 'signalp',
  'lipop1_bin': 'LipoP',
  'tmhmm_bin': 'tmhmm',
  'helix_programs': ['tmhmm'],
#' helix_programs': ['tmhmm', 'memsat3'],
  'barrel_programs': ['bomp', 'tmbeta'],
# 'barrel_programs': ['bomp', 'tmbeta', 'tmbhunt'],
  'bomp_cutoff': 1,
  'tmbhunt_cutoff': 0.5,
  'memsat3_bin': 'runmemsat',
  'hmmsearch3_bin': 'hmmsearch',
  'hmm_profiles_dir': '%(hmm_profiles)s',
  'hmm_evalue_max': 0.1,
  'hmm_score_min': 10,
  'terminal_exposed_loop_min': 50,
  'internal_exposed_loop_min': 100,
}
"""


def get_params():
  config = os.path.join(module_dir, 'inmembrane.config')
  if not os.path.isfile(config):
    log_stderr("# Couldn't find inmembrane.config file")
    log_stderr(
         "# So, will generate a default config " + config)
    abs_hmm_profiles = os.path.join(module_dir, 'hmm_profiles')
    default_str = default_params_str % \
        { 'hmm_profiles': abs_hmm_profiles }
    open(config, 'w').write(default_str)
  else:
    log_stderr("# Loading existing inmembrane.config")
  params = eval(open(config).read())
  return params


def init_output_dir(params):
  """
  Creates a directory for all output files and makes it the current 
  working directory. copies the input sequences into it as 'input.fasta'.
  """
  if dict_get(params, 'out_dir'):
    base_dir = params['out_dir']
  else:
    base_dir = '.'.join(os.path.splitext(params['fasta'])[:-1])
    params['out_dir'] = base_dir
  if not os.path.isdir(base_dir):
    os.makedirs(base_dir)

  if not dict_get(params, 'csv'):
    basename = '.'.join(os.path.splitext(params['fasta'])[:-1])
    params['csv'] = basename + '.csv'
  params['csv'] = os.path.abspath(params['csv'])

  fasta = "input.fasta"
  shutil.copy(params['fasta'], os.path.join(base_dir, fasta))
  params['fasta'] = fasta

  shutil.copy(os.path.join(module_dir, 'inmembrane.config'), base_dir)

  os.chdir(base_dir)


def create_protein_data_structure(fasta):
  """
  From a FASTA file, creates a dictionary using the ID of each sequence
  in the fasta file. Also returns a list of ID's in the same order as
  that in the file.
  """
  seqids = []
  seqid = None
  proteins = {}
  for l in open(fasta):
    if l.startswith(">"):
      seqid, name = parse_fasta_header(l)
      seqids.append(seqid)
      proteins[seqid] = {
        'seq':"",
        'name':name,
      }
      continue
    if seqid is not None:
      words = l.split()
      if words:
        proteins[seqid]['seq'] += words[0]
  return seqids, proteins

  
def write_to_csv(csv, seqids, proteins):
  f = open(csv, 'w')
  for seqid in seqids:
    protein = proteins[seqid]
    f.write('%s,%s,%s,"%s"\n' % \
        (seqid, 
         protein['category'], 
         protein['details'],
         protein['name']))
  f.close()


def process(params):
  protocol_py = 'protocols/' + params['protocol'] + '.py'
  if not os.path.isfile(protocol_py):
    raise IOError("Couldn't find protcols/" + protocol_py)
  exec('import protocols.%s as protocol' % (params['protocol']))
  protocol.init(params)

  init_output_dir(params)

  seqids, proteins = create_protein_data_structure(params['fasta'])

  # TODO: this loop needs to be run within the protocol,
  #       since for some protocols not all plugins
  #       will be run for every sequence, dependent
  #       on the outcome of a previous analysis
  #       eg. protocol.run(params, proteins)
  for feature in params['features']:
    exec('%s(params, proteins)' % feature)

  for seqid in seqids:
    protein = proteins[seqid]
    details, category = \
        protocol.post_process_protein(params, protein)
    if details.endswith(';'):
      details = details[:-1]
    if details is '':
      details = "."
    protein['details'] = details
    protein['category'] = category
    log_stdout('%-15s   %-13s  %-50s  %s' % \
        (seqid, 
         protein['category'], 
         protein['details'],
         protein['name'][:60]))

  write_to_csv(params['csv'], seqids, proteins)
    

if __name__ == "__main__":
  parser = OptionParser()
  (options, args) = parser.parse_args()
  params = get_params()
  if ('fasta' not in params or not params['fasta']) and not args:
    print description
    parser.print_help()
    sys.exit(1)
  if 'fasta' not in params or not params['fasta']:
    params['fasta'] = args[0]
  process(params)

