#!/usr/bin/env python
'''
    Small bin to merge ecal and sdhcal trees from common test beam of 09/2018 to find the time difference for each event between the two calorimeters.
    Since they don't have the same number of entries (an entry being a recorded event in each calorimeter) but they have the same number of trigger/spill
    This script goes trhough each trigger/spill and create an entry for each potential common ecal-sdhcal events.
    e.g if there is 3 events in the sdhcal and 4 in the ecal for a given trigger the new tree will have 12 entry:
        entry0 = sdhcal0 , ecal0
        entry1 = sdhcal0 , ecal1
        entry1 = sdhcal0 , ecal2
        ...
        entry10 = sdhcal2, ecal2
        entry11 = sdhcal2, ecal3

    All branches names are prepended by the name of the calorimeter. i.e `event` branch in the ecal tree becomes `ecal_event` in the common tree.
python correctEcal_Bcid.py --run_list 744323 --common_file_format /eos/user/a/apingaul/CALICE/Data/SPS_09_2018/Trivent/Common_{run_number}.root --output_file_format /eos/user/a/apingaul/CALICE/Data/SPS_09_2018/Trivent/Common_{run_number}_bcid_corrected.root --use_xroot
 python makeCommonEventTree.py --run_list 744318 --hcal_file_format /eos/user/a/apingaul/CALICE/Data/SPS_09_2018/Trivent/DHCAL_Trivent_Ecal_{run_number}.root --ecal_file_format /eos/project/s/siw-ecal/TB2018-09/Common/ECAL/PiPlus_70GeV/{run_number}__build.root --output_file_format /eos/user/a/apingaul/CALICE/Data/SPS_09_2018/Trivent/Common_{run_number}.root --ecal_tree_name ecal --hcal_tree_name sdhcal --output_tree_name common --use_xroot --ecal_slab_cut 3
python makeCommonEventTree.py --run_list 744211 744283 --hcal_file_format /eos/user/a/apingaul/CALICE/Data/SPS_09_2018/Trivent/DHCAL_Trivent_Ecal_{run_number}.root --ecal_file_format /eos/project/s/siw-ecal/TB2018-09/Common/ECAL/offset_twiki/Muon_200GeV/{run_number}__build.root --output_file_format /eos/user/a/apingaul/CALICE/Data/SPS_09_2018/Trivent/Common_{run_number}.root --ecal_tree_name ecal --hcal_tree_name sdhcal --output_tree_name common --triggers 100 --use_xroot --select_muons --ecal_slab_cut 3
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
    parser.add_argument(
        '-f',
        '--hcal_file_format',
        help=
        'Path format to sdhcal file, need {run_number} somewhere in the path to be replaced by the value of -r. Accept xroot url',
        required=True,
        default='/eos/user/a/apingaul/CALICE/Data/SPS_09_2018/Trivent/DHCAL_Trivent_Ecal_{run_number}.root')
    parser.add_argument(
        '-e',
        '--ecal_file_format',
        help=
        'Path format to ecal file, need {run_number} somewhere in the path to be replaced by the value of -r. Accept xroot url',
        required=True,
        default='/eos/project/s/siw-ecal/TB2018-09/Common/ECAL/offset_twiki/Muon_200GeV/{run_number}__build.root')
    parser.add_argument('-o',
                        '--output_file_format',
                        help='''
                        Path format to output file, need {run_number} somewhere in the path to be replaced by the value of -r.
                        Accept xroot url
                        if --triggers is set, '{triggers}_triggers' is appended to the file name''',
                        required=True,
                        default='/eos/user/a/apingaul/CALICE/Data/SPS_09_2018/Trivent/Common_{run_number}.root')

    # Optional
    parser.add_argument('-n', '--triggers', type=int, help='Number of triggers/spill to analyse', default=0)
    parser.add_argument('--xroot_url', default='root://eosuser.cern.ch/')
    parser.add_argument('--use_xroot', action='store_true', default=False)
    parser.add_argument('--ecal_tree_name', help='Name of the ecal tree', default='ecal')
    parser.add_argument('--hcal_tree_name', help='Name of the sdhcal tree', default='sdhcal')
    parser.add_argument('--output_tree_name', help='Name of the output tree', default='common')
    parser.add_argument('--select_muons',
                        action='store_true',
                        default=False,
                        help='Apply some cuts to select mostly muons')
    parser.add_argument('--ecal_slab_cut', default=3)

    return parser.parse_args()


def main(args=None):

    args = parse_args()
    run_list = args.run_list if isinstance(args.run_list, list) else list(args.run_list)
    logger.info('Processing runs: %s' % run_list)

    # List of branches we want to use
    hcal_branches = ['TrigNum', 'EvtNum', 'EvtRevBcid', 'NHits']  # List of branches we want to use
    ecal_branches = ['spill', 'event', 'bcid', 'nhit_slab']

    pbar = tqdm(run_list, unit='run')
    for run in pbar:
        pbar.set_description('Processing run %s' % run)
        # Read data directly from eos, you need to be identified with a kerberos5 token to use this feature
        hcal_file_name = args.hcal_file_format.format(run_number=run)
        ecal_file_name = args.ecal_file_format.format(run_number=run)
        out_file_name = args.output_file_format.format(run_number=run)
        if args.triggers != 0:
            out_file_name.replace('.root', '_{}trig.root'.format(args.triggers))
        if args.use_xroot:
            hcal_file_name = args.xroot_url + hcal_file_name
            ecal_file_name = args.xroot_url + ecal_file_name
            out_file_name = args.xroot_url + out_file_name

        # Get Trees for both calo and convert them to pandas DataFrame.
        # Define some cuts to fetch the data
        # Take a sample of the hit distribution in sdhcal layers to determine the number of layer in the current run
        hcal_tree = uproot.open(hcal_file_name)[args.hcal_tree_name]
        df_hcal_sample = hcal_tree.pandas.df('HitK', entrystop=1000)
        hcal_layers = df_hcal_sample['HitK'].nunique()
        del df_hcal_sample, hcal_tree  # No need to keep it around
        hcal_cut = 'NHits/{hcal_layers}>1'.format(hcal_layers=hcal_layers)
        density_cut = 2.5
        if args.select_muons:
            hcal_cut += ' and NHits/{hcal_layers} < {density_cut}'.format(hcal_layers=hcal_layers,
                                                                          density_cut=density_cut)

        ecal_cut = 'nhit_slab>{}'.format(args.ecal_slab_cut)

        # Open the root files, read the correct tree and select the data in one go
        df_hcal = uproot.open(hcal_file_name)[args.hcal_tree_name].pandas.df(hcal_branches).query(hcal_cut)
        df_ecal = uproot.open(ecal_file_name)[args.ecal_tree_name].pandas.df(ecal_branches).query(ecal_cut)

        # Rename branches/columns to avoid confusion when merging the data
        df_hcal.rename(columns=lambda key: 'sdhcal_' + key, inplace=True)
        df_ecal.rename(columns=lambda key: 'ecal_' + key, inplace=True)

        data = []
        nTriggers = df_hcal['sdhcal_TrigNum'].max() if args.triggers == 0 else args.triggers

        # Remove the call to tqdm() if you don't want the progress bar
        pbar_trigger = tqdm(range(nTriggers), unit='Triggers')
        for trigger in pbar_trigger:
            pbar_trigger.set_description('Processing trigger: %s' % trigger)
            df_hcalTrig = df_hcal.query('sdhcal_TrigNum=={trigger}'.format(trigger=trigger))
            df_ecalTrig = df_ecal.query('ecal_spill=={trigger}'.format(trigger=trigger))

            for iHcal in range(len(df_hcalTrig)):
                hcalEvt = df_hcalTrig.iloc[iHcal]
                for iEcal in range(len(df_ecalTrig)):
                    ecalEvt = df_ecalTrig.iloc[iEcal]
                    temp = pd.concat([ecalEvt, hcalEvt])  # Merge the data
                    temp['delta_revbcid'] = ecalEvt.ecal_bcid - hcalEvt.sdhcal_EvtRevBcid
                    data.append(temp)
        df_common = pd.DataFrame(data)
        del data

        # Save using root_pandas since uproot is not yet able to do it

        # Move the root_pandas import here otherwise ROOT will mess with argparse even when cmd line parsing is disabled...
        # # Seriously ROOT?
        # # Disable cmd line parsing before other ROOT deps are loaded
        from ROOT import PyConfig
        IgnoreCommandLineOptions = True
        from root_pandas import to_root  # Needed to write to root file until uproot implement it

        df_common.to_root(out_file_name, key=args.output_tree_name)
        # df_ecal.to_root(out_file_name, key=args.ecal_tree_name, mode='a')
        # df_hcal.to_root(out_file_name, key=args.hcal_tree_name, mode='a')


# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    main()
