import helpers

def annotate_signalp4(params, proteins):
  for seqid in proteins:
    proteins[seqid]['is_signalp'] = False
    proteins[seqid]['signalp_cleave_position'] = None

  signalp4_out = 'signalp.out'
  cmd = '%(signalp4_bin)s -t %(signalp4_organism)s  %(fasta)s' % \
             params
  helpers.run(cmd, signalp4_out)

  for line in open(signalp4_out):
    if line.startswith("#"):
      continue
    words = line.split()
    seqid = helpers.parse_fasta_header(">"+words[0])[0]
    proteins[seqid]['signalp_cleave_position'] = int(words[4])
    if (words[9] == "Y"):
      proteins[seqid]['is_signalp'] = True

  return proteins
    
