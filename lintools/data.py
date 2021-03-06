import MDAnalysis
import sys
from rdkit import Chem
from MDAnalysis.analysis import distances
from MDAnalysis.lib.NeighborSearch import AtomNeighborSearch
import operator
import os


class Data(object):
    """
    This module is used to import datafiles such as topology, trajectory and mol files,
    as well as several auxillary functions - reorder protein resids and find closest ligand
    atoms.
    """
    __version__ = "09.2016"
    def __init__(self):
        self.dict_of_plotted_res = {}
        self.closest_atoms = {}
        self.ring_number = 1
    def load_topology(self,topology):
        """
        Loads the topology file (e.g. GRO,PDB,INPCRD) as a MDAnalysis Universe,
        checks if it can be loaded. Needs to be run before the equivalent function
        topol.load_trajectory() and provides the snapshot that is going to be used
        for final residue placement - i.e. the residue coordinates for placement
        are taken from this file.
            Takes:
              * topology * - a topology file e.g. GRO, PDB, INPCRD, CARD, DMS
            Output:
              * self.universe * - MDAnalysis Universe
        """

        try:
            self.universe = MDAnalysis.Universe(topology)
        except ValueError:
            print "Check your topology file - it is either missing or misspelled."
            sys.exit()
    def load_trajectory(self,trajectory):
        """
        Loads the trajectory files e.g. XTC, DCD, TRJ together with the topology
        file as a MDAnalysis Universe. This will only be run if a trajectory has
        been submitted for analysis.
            Takes:
                * topology * - a topology file e.g. GRO, PDB, INPCRD, CARD, DMS
                * trajectory * - a trajectory file e.g. XTC, DCD, TRJ
            Output:
                * self.universe * - an MDAnalysis Universe consisting from the
                topology and trajectory file.
        """

        try:
            self.universe.load_new(trajectory)
        except IOError, ValueError:
            print "Check you trajectory file " + trajectory +"- it might be missing or misspelled."
    def load_mol(self, mol_file):
        """Loads a MOL file of the ligand (submitted by user) into RDKit environment.
            Takes:
                * mol_file * - user submitted MOL file of the ligand
            Output:
                * self.mol_mda * - the ligand as MDAnalysis Universe,
                * self.mol * - the ligand in RDKit environment as Mol object.
        """
        #Check if MOL file has been provided correctly and can be loaded in MDAnalysis
        if mol_file is None:
            mol_file = "lig.mol"

        self.mol = Chem.MolFromMolFile(mol_file,removeHs=False,sanitize=False)
        try:
            self.mol.UpdatePropertyCache(strict=False)
        except AttributeError:
            assert self.mol != None, "The MOL file could not be imported in RDKit environment. Suggestion: Check the atomtypes."
        assert self.mol != None, "The MOL file could not be imported in RDKit environment."

    def rename_ligand(self,ligand_name,mol_file):
        """
        Get an atom selection for the selected from both topology and trajectory. Rename the ligand LIG
        to help with ligand names that are not standard, e.g. contain numbers.
            Takes:
                * ligand_name * - MDAnalysis atom selection for the ligand selected by user
            Output:
                * self.ligand * - renamed ligand with resname LIG,
                * self.ligand_noH * - renamed ligand with resname LIG and without H atoms (these are not
                present in the final 2D representation and are therefore excluded from some analysis scripts.)
        """

        self.universe.ligand = self.universe.select_atoms(ligand_name)
        #Both resname and resnames options need to be reset in order for complete renaming.
        self.universe.ligand.residues.resnames = "LIG"
        self.universe.ligand.resname = "LIG"
        if mol_file is None:
            self.universe.ligand.write("lig.pdb")

            os.system("babel -ipdb lig.pdb -omol lig.mol ")


    def renumber_system(self, offset):
        """
        The residue numbers of the protein can be reformated in case of misallignment with the convention.
            Takes:
                 * offset * - a number that represents by how many residues the numbering has to be shifted.
        """

        self.universe.protein = self.universe.select_atoms("protein")
        self.universe.protein.residues.resids = self.universe.protein.residues.resids+int(offset)

    def define_residues_for_plotting_topology(self,cutoff):
        """
        This function defines the residues for plotting in case only a topology file has been submitted.
        In this case the residence time analysis in not necessary and it is enough just to find all
        residues within a cutoff distance.
            Takes:
                * cutoff * - cutoff distance in angstroms that defines native contacts
            Output:
                *
        """

        #self.protein_selection = self.universe.select_atoms('all and around '+str(cutoff)+' (segid '+str(self.universe.ligand.segids[0])+' and resid '+str(self.universe.ligand.resids[0])+')')
        #The previous line was not working on some examples for some reason - switch to more efficient Neighbour Search
        n = AtomNeighborSearch(self.universe.select_atoms('protein and not name H* or (segid '+str(self.universe.ligand.segids[0])+' and resid '+str(self.universe.ligand.resids[0])+')'), bucket_size=10)
        self.protein_selection = n.search(self.universe.ligand,cutoff,level="A")
        for atom in self.protein_selection.atoms:
                #for non-analysis plots
                residue = (atom.resname, str(atom.resid), atom.segid)
                if residue not in self.dict_of_plotted_res.keys() and atom not in self.universe.ligand.atoms:
                    self.dict_of_plotted_res[residue]=[1]
        assert len(self.dict_of_plotted_res)!=0, "Nothing to draw for this ligand (residue number: "+ self.universe.ligand.resids[0] +" on the chain "+ self.universe.ligand.segids[0] +") - check the position of your ligand within the topology file."


    def find_the_closest_atoms(self,topology):
        """
        This function defines the ligand atoms that are closest to the residues that will be plotted
        in the final graph.
        """

        # The measurements are made to ligand molecule without hydrogen atoms (ligand_noH) because the
        # hydrogen atoms are not plotted in the final graph
        self.universe.load_new(topology)
        self.universe.ligand_noH = self.universe.ligand.select_atoms("not name H*")
        ligand_positions = self.universe.ligand_noH.positions

        for residue in self.dict_of_plotted_res.keys():
            residue_selection = self.universe.select_atoms("resname "+residue[0]+" and resid "+residue[1]+" and segid "+ residue[2])
            residue_positions = residue_selection.positions
            dist_array = MDAnalysis.analysis.distances.distance_array(ligand_positions,residue_positions)
            min_values_per_atom={}
            i=0
            for atom in self.universe.ligand_noH:
                min_values_per_atom[atom.name]=dist_array[i].min()
                i+=1
            sorted_min_values = sorted(min_values_per_atom.items(), key=operator.itemgetter(1))
            self.closest_atoms[residue]=[(sorted_min_values[0][0],sorted_min_values[0][1])]
    def load_data(self, topology, mol_file, ligand_name, offset=0):
        """
        This function loads all relevant data - except trajectories since those are dealt with one at a time.
        Therefore, this process only needs to be done once, and every time a trajectory needs to be loaded, it
        can be loaded seperataly and the Data object can be shared across LINTools processes.
        """

        self.load_topology(topology)
        self.renumber_system(offset)
        self.rename_ligand(ligand_name,mol_file)
        self.load_mol(mol_file)

    def analyse_topology(self,topology, cutoff=3.5):
        """
        In case user wants to analyse only a single topology file, this process will determine the residues
        that should be plotted and find the ligand atoms closest to these residues.
        """

        self.define_residues_for_plotting_topology(cutoff)
        self.find_the_closest_atoms(topology)
