#!/usr/bin/env python
'''
    Small bin to merge ecal and sdhcal trees from common test beam of 09/2018 to find the time difference for each event between the two calorimeters.
'''
from __future__ import (absolute_import, division, print_function)  #, unicode_literals)

import platform
import uproot
import pandas as pd
from tqdm.auto import tqdm  # Progressbar
import argparse

if float(platform.python_version()[0:3]) >= 3.5:
    from loguru import logger
else:
    import logging
    logger = logging.getLogger(__file__)
    FORMAT = "[%(name)s:%(funcName)s: line %(lineno)s] - %(levelname)s - %(message)s"
    logging.basicConfig(format=FORMAT)
    logger.setLevel(logging.DEBUG)


def parse_args():
    # Required
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--run_list', nargs='+', type=int, help='can be a list of one...', required=True)
    parser.add_argument('-f',
                        '--common_file_format',
                        help='''
                        Path format to common file, need {run_number} somewhere in the path to be replaced by the value of -r.
                        Accept xroot url''',
                        required=True,
                        default='/eos/user/a/apingaul/CALICE/Data/SPS_09_2018/Trivent/Common_{run_number}.root')
    parser.add_argument(
        '-o',
        '--output_file_format',
        help='''
        Path format to output file, need {run_number} somewhere in the path to be replaced by the value of -r. Accept xroot url''',
        required=True,
        default='/eos/user/a/apingaul/CALICE/Data/SPS_09_2018/Trivent/Common_{run_number}_bcid_corrected.root')
    # Optional
    parser.add_argument('-n', '--triggers', type=int, help='Number of triggers/spill to analyse', default=0)
    parser.add_argument('--xroot_url', default='root://eosuser.cern.ch/')
    parser.add_argument('--use_xroot', action='store_true', default=False)
    parser.add_argument('--common_tree_name', help='Name of the input tree', default='common')
    parser.add_argument('--output_tree_name', help='Name of the output tree', default='common')
    parser.add_argument('--clock_cut', type=int, help='', default=8192)
    parser.add_argument('--ecal_start', type=int, help='', default=2488)
    return parser.parse_args()


def correct_bcid(ecal_bcid, hcal_bcid, ecal_start, clock_cut):
    ''' ecal_bcid < 2488 : Need to add 8192 from the beginning of the run.
        2488< ecal_bcid < 2488 + 8192 : Need to add 8192 after the first 8192 clocks.
        ecal_bcid > 2488 + 8192 : No correction
    '''
    if ecal_bcid < ecal_start:
        bcid_corrected = ecal_bcid + (1 + int(hcal_bcid / clock_cut)) * clock_cut
    elif ecal_bcid < ecal_start + clock_cut:
        bcid_corrected = ecal_bcid + int(hcal_bcid / clock_cut) * clock_cut
    elif hcal_bcid > 2 * clock_cut:
        bcid_corrected = ecal_bcid + int(hcal_bcid / clock_cut - 1) * clock_cut
    else:
        bcid_corrected = ecal_bcid

    return bcid_corrected


def main(args=None):

    args = parse_args()
    run_list = args.run_list if isinstance(args.run_list, list) else list(args.run_list)
    logger.info('Processing runs: %s' % run_list)

    pbar = tqdm(run_list, unit='run')
    for run in pbar:
        pbar.set_description('Processing run %s' % run)
        common_file_name = args.common_file_format.format(run_number=run)
        out_file_name = args.output_file_format.format(run_number=run)

        if args.triggers != 0:
            out_file_name.replace('.root', '_{}trig.root'.format(args.triggers))

        # Read data directly from eos, you need to be identified with a kerberos5 token to use this feature
        if args.use_xroot:
            common_file_name = args.xroot_url + common_file_name
            out_file_name = args.xroot_url + out_file_name

        df_common = uproot.open(common_file_name)[args.common_tree_name].pandas.df()

        tqdm.pandas(desc="Correcting ecal_bcid", unit=' Event')
        df_common['ecal_bcid_corrected'] = df_common.progress_apply(
            lambda row: correct_bcid(row['ecal_bcid'], row['sdhcal_EvtRevBcid'], args.ecal_start, args.clock_cut),
            axis=1)
        tqdm.pandas(desc="Computing delta_revbcid", unit=' Event')
        df_common['delta_revbcid_corrected'] = df_common.progress_apply(
            lambda row: row['ecal_bcid_corrected'] - row['sdhcal_EvtRevBcid'], axis=1)

        # Save using root_pandas since uproot is not yet able to do it
        # Move the root_pandas import here otherwise ROOT will mess with argparse even when cmd line parsing is disabled...
        # # Seriously ROOT?
        # # Disable cmd line parsing before other ROOT deps are loaded
        from ROOT import PyConfig
        IgnoreCommandLineOptions = True
        from root_pandas import to_root  # Needed to write to root file until uproot implement it

        df_common.to_root(out_file_name, key=args.output_tree_name)


# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    main()
