from numpy.testing import TestCase, assert_equal, assert_almost_equal
import unittest
import os
from lintools.lintools.topol import Topol_Data
from lintools.lintools.analysis.occurrence import Occurrence_analysis
from lintools.lintools.plots import Plots
from lintools.lintools.testsuite.datafiles import *
import numpy as np

class TestCheckPlots(TestCase):
    def setUp(self):
        self.topology = Topol_Data(PDB,None,None,0)
        self.u = self.topology.universe
        self.ligand = self.u.select_atoms("resname LDP")
        self.ligand.resname = "LIG"
        self.ligand.resnames = "LIG"
        self.topology.define_ligand(self.ligand)
        self.topology.find_res_to_plot(3.5)
        self.topology.get_closest_ligand_atoms()
        self.plots = Plots(self.topology)
    def tearDown(self):
        del self.topology
        del self.plots
    def test_amino_plots(self):
    	self.plots.define_amino_acids()
    	self.plots.plot_amino_diagramms()
    	amino_acid_type = {'ALA117': 'hydrophobic',
 'ASP121': 'acidic',
 'ASP46': 'acidic',
 'PHE325': 'aromatic',
 'PHE43': 'aromatic',
 'SER421': 'polar',
 'SER422': 'polar',
 'TYR124': 'aromatic',
 'VAL120': 'hydrophobic'}
        assert_equal(self.plots.amino_acid_type,amino_acid_type)
    def test_domain_plots(self):
    	self.plots.define_domains(DOM_FILE_4XP1,3.5)
        res_within_domain = {'ALA117': [2, 'TMH 2', '#D9774B', 'N'],
 'ASP121': [2, 'TMH 2', '#D9774B', ['Y\n']],
 'ASP46': [1, 'TMH 1\n', '#78D035', 'N'],
 'PHE325': [0, 'No specified domain', '#A9A9A9', 'N'],
 'PHE43': [1, 'TMH 1\n', '#78D035', ['Y\n']],
 'SER421': [3, 'Chain B', '#889DCC', 'Y\n'],
 'SER422': [3, 'Chain B', '#889DCC', ['Y\n']],
 'TYR124': [2, 'TMH 2', '#D9774B', 'N'],
 'VAL120': [2, 'TMH 2', '#D9774B', ['Y\n']]}
        assert_equal(res_within_domain,self.plots.residues_within_domain)
    	self.plots.plot_domains_diagramms()
        plotted_domains = [[4, 'Binding site', '#A9A9A9', 'Y\n'],
 [0, 'No specified domain', '#A9A9A9', 'N'],
 [2, 'TMH 2', '#D9774B', ['Y\n']],
 [1, 'TMH 1\n', '#78D035', ['Y\n']],
 [1, 'TMH 1\n', '#78D035', 'N'],
 [2, 'TMH 2', '#D9774B', 'N'],
 [3, 'Chain B', '#889DCC', 'Y\n'],
 [3, 'Chain B', '#889DCC', ['Y\n']]]
    	assert_equal(self.plots.plotted_domains,plotted_domains)

class TestCheckPlotsWithTrajs(TestCase):
    def setUp(self):
        self.topology = Topol_Data(TOPOLOGY,[TRAJ_20FR,TRAJ_50FR],None,0)
        self.u = self.topology.universe
        self.ligand = self.u.select_atoms("resname UNK")
        self.ligand.resname = "LIG"
        self.ligand.resnames = "LIG"
        self.topology.define_ligand(self.ligand)
        self.occurrence = Occurrence_analysis(TOPOLOGY, [TRAJ_20FR,TRAJ_50FR], self.ligand, 3.5, 0, self.topology)
        self.occurrence.get_closest_residues(30)
        self.plots = Plots(self.topology)
    def tearDown(self):
        del self.topology
        del self.occurrence
        del self.plots
    def test_clocks_plots(self):
        self.plots.plot_clock_diagramms()
        with open(CLOCK_280,"r") as f:
            lines = f.readlines()
            self.out_test_svg = " ".join(map(str,lines[2:-1]))
            f.close()
        with open("280.svg","r") as f:
            lines = f.readlines()
            self.out_svg_to_test = " ".join(map(str,lines[2:-1]))
            f.close()
        assert_equal(self.out_test_svg,self.out_svg_to_test)