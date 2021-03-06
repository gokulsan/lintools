import rdkit
from rdkit import Chem
import numpy as np
import MDAnalysis
from collections import namedtuple, defaultdict
import os
from timeit import default_timer as timer
import maths_functions as math
import csv
"""
The code in this module has been inspired by PLIP (Protein Ligand Interaction Profiler) from Salentin et al. Nucl. Acids Res. (2015).
PLIP is originally published under the Apache License v2 and is available at https://github.com/ssalentin/plip
"""
class PiStacking(object):
    __version__= "09.2016"
    """This module analyses pi-pi interactions - the stacking of aromatic rings. First, aromatic rings are determined using rdkit for both ligand and protein
    - residues TRP,HIS,PHE,TYR. Then all possible combinations of pi-pi interactions are analysed through the distance between centers of geometry, angle of
    the ring plane and offset distance. If these fullfil the requirements for either 'P' - parallel stacking or 'T' - T-shaped stacking the parameters for these
    interactions are saved in a named tuple. This tuple can be converted into numpy array (make_table) which is then used to determine the total amount of pi-stacking in a
    simulation (count_by_time) or determine how many times a certain interaction occcurs (count_by_type).

    Takes:
        * topology data object * - information about system (lintools.Data object)
        * trajectory * - list of trajectories
        * start_frame_num * - list^^ of frame numbers for start of analysis (Opt)
        * end_frame_num * - list^^ of frame numbers for end of analysis (Opt)
        * skip * - list^^ of numbers of how many frames should be skipped for this analysis (Opt)
        * analysis_cutoff * - a fraction of simulation time a feature has to be present for to be
            plotted in the final figure

    ^^ The reason these values are lists is because several trajectories can be submitted for
    analysis and different values could be required for each simulation. Therefore, similarly
    as with trajectories, start, end and skip variables are submitted as lists with values
    corresponding for each trajectory.

    Example: trajectory = ["1.xtc","2.xtc"] #Both are 1000 frames, but the user only wants to
             analyse second half the the second trajectory
             start = [0(for the first traj),500(for the second traj)]
             Other values can be left as default.

    Output:
        * self.pistacking * - numpy array of pi-stacking interactions searchable by keywords
        * self.pistacking_by_time * - numpy array of total pi-stacking interactions per frame
        * self.pistacking_by_type * - numpy array of total count of each pi-stacking interaction
        * self.pi_contacts_for_drawing * - list of the pi-stacking interactions to be included
        in the final figure after calculating frequency of each interaction and comparing it to
        analysis cutoff.
         """
    def __init__(self,topology_data_object,trajectory,start_frame_num,end_frame_num,skip,analysis_cutoff):
        self.topology_data = topology_data_object
        self.max_distance = 7.5
        self.max_angle_dev = 30
        self.max_offset = 2.0
        self.trajectory = trajectory
        self.start_frame_num = start_frame_num
        self.end_frame_num = end_frame_num
        self.skip = skip
        self.pistacking={}
        self.pistacking_by_time = {}
        self.pistacking_by_type = {}

        self.detect_aromatic_rings_in_ligand()
        self.detect_aromatic_rings_in_protein()
        self.define_all_protein_rings()
        self.find_all_pistacking_pairs()
        self.get_pistacking_frequency(analysis_cutoff)


    def detect_aromatic_rings_in_ligand(self):
        """Using rdkit to detect aromatic rings in ligand - size 4-6 atoms and all atoms are part of the ring. Saves this data in self.ligrings."""
        self.ligrings = {}
        try:
            ring_info = self.topology_data.mol.GetRingInfo()
            self.ligand_ring_num = ring_info.NumRings()
        except Exception as e:
            m = Chem.MolFromPDBFile("lig.pdb")
            ring_info = m.GetRingInfo()
            self.ligand_ring_num = ring_info.NumRings()
        i=0
        for ring in range(self.ligand_ring_num):
            if 4 < len(ring_info.AtomRings()[ring]) <= 6 and  False not in [self.topology_data.mol.GetAtomWithIdx(x).GetIsAromatic() for x in ring_info.AtomRings()[ring]]: #narrow ring definition
                atom_ids_in_ring = []
                for atom in ring_info.AtomRings()[ring]:
                    atom_ids_in_ring.append(self.topology_data.universe.ligand.atoms[atom].name)
                self.ligrings[i]=atom_ids_in_ring
                i+=1

    def detect_aromatic_rings_in_protein(self):
        """Use rdkit to detect aromatic rings in protein. A (relatively) simpler case, since only 4 of 20 aa have rings.
        Since different forcefields can have different atom names, each of 4 aromatic residues is extracted as PDB file
        and the aromatic rings are detected for each. The case is trickier with TRP, since this residue has two aromatic rings -
        these are considered separately.
        Data is saved in self.rings dictionary."""
        self.rings = {}
        for ar_resname in ["PHE","TRP","TYR","HIS"]:
            for res in self.topology_data.universe.residues:
                if res.resname == ar_resname:
                    aromatic_aa = self.topology_data.universe.select_atoms("resname "+res.resname+" and resid "+str(res.resid)+" and segid "+ res.segid)
                    aromatic_aa.write(ar_resname+".pdb")
                    break
        for ar_resname in ["PHE","TRP","TYR","HIS"]:
            try:
                arom_aa_rdkit = Chem.MolFromPDBFile(ar_resname+".pdb")
                arom_aa_mda = MDAnalysis.Universe(ar_resname+".pdb")
                ring_info = arom_aa_rdkit.GetRingInfo()
                number_of_rings = ring_info.NumRings()
                for ring in range(number_of_rings):
                    atom_names_in_ring = []
                    for atom in ring_info.AtomRings()[ring]:
                        atom_names_in_ring.append(arom_aa_mda.atoms[atom].name)
                    self.rings[(ar_resname,ring)]=atom_names_in_ring
            except IOError:
                continue

    def define_all_protein_rings(self):
        """Make MDAnalysis atom selections for rings in protein residues that will be plotted in the final figure - since they are the only ones that
        should be analysed.
        Saves the rings in self.protein_rings dictionary.
        """
        self.protein_rings = {}
        i=0
        for residue in self.topology_data.dict_of_plotted_res:
            for ring in self.rings:
                if ring[0]==residue[0]:
                    atom_names =""
                    for atom in self.rings[ring]:
                        atom_names = atom_names+" "+atom
                    self.protein_rings[i]= self.topology_data.universe.select_atoms("resname "+residue[0]+" and resid "+residue[1]+" and segid "+ residue[2]+" and name "+atom_names)
                    i+=1



    def find_all_pistacking_pairs(self):
        """Main analysis function. Analyses each frame in the trajectory in search for pi-pi interactions between previously defined rings on
        protein residues and ligand molecule. """
        data = namedtuple("pistacking","frame time proteinring ligandring distance angle offset type resname resid segid")
        i=0
        if self.trajectory==[]:
            self.trajectory = [self.topology_data.universe.filename]
            self.start_frame_num=[None]
            self.end_frame_num = [None]
            self.skip =[None]
        for traj in self.trajectory:
            self.timeseries=[]
            self.timesteps=[frame.time for frame in self.topology_data.universe.trajectory[self.start_frame_num[i]:self.end_frame_num[i]:self.skip[i]]]
            start = timer()
            self.topology_data.load_trajectory(traj)
            for prot_ring in self.protein_rings:
                    for ring in self.ligrings:
                        l = self.get_ligand_ring_selection(ring)
                        p = self.protein_rings[prot_ring]
                        for frame in self.topology_data.universe.trajectory[self.start_frame_num[i]:self.end_frame_num[i]:self.skip[i]]:
                            lig_norm_vec = math.prepare_normal_vectors(l)
                            protein_norm_vec = math.prepare_normal_vectors(p)
                            dist = math.euclidean3d(l.center_of_geometry(),p.center_of_geometry())

                            a = math.vecangle(lig_norm_vec,protein_norm_vec)
                            angle = min(a, 180 - a if not 180 - a < 0 else a)

                            #Measure offset
                            proj1 = math.projection(lig_norm_vec,l.center_of_geometry(),p.center_of_geometry())
                            proj2 = math.projection(protein_norm_vec,p.center_of_geometry(),l.center_of_geometry())
                            offset = min(math.euclidean3d(proj1,l.center_of_geometry()), math.euclidean3d(proj2,p.center_of_geometry()))


                            if dist < self.max_distance:
                                if 0 < angle < self.max_angle_dev and offset < self.max_offset:
                                    contacts = data(frame=frame.frame, time=frame.time, proteinring=tuple([a.id for a in p]), ligandring=tuple([a.id for a in l]), distance=dist, angle=angle, offset=offset,
                                                    type="P",resname=self.protein_rings[prot_ring].residues.resnames[0],
                                                    resid=self.protein_rings[prot_ring].residues.resids[0], segid=self.protein_rings[prot_ring].residues.segids[0])
                                    self.timeseries.append(contacts)
                                if 90 - self.max_angle_dev < angle < 90 + self.max_angle_dev and offset < self.max_offset:
                                    contacts = data(frame=frame.frame, time=frame.time, proteinring=tuple([a.id for a in p]), ligandring=tuple([a.id for a in l]), distance=dist, angle=angle, offset=offset,
                                                    type="T",resname=self.protein_rings[prot_ring].residues.resnames[0],
                                                    resid=self.protein_rings[prot_ring].residues.resids[0], segid=self.protein_rings[prot_ring].residues.segids[0])
                                    self.timeseries.append(contacts)
            self.pistacking[i] = self.make_table()

            self.pistacking_by_time[i] = self.count_by_time()
            self.pistacking_by_type[i] = self.count_by_type()
            self.write_output_files(i)
            i+=1
        end = timer()
        print "Pi-Stacking:"+str(end-start)

    def make_table(self):
        """Make numpy array from timeseries data."""
        num_records = int(np.sum([1 for frame in self.timeseries]))
        dtype = [
                ("frame",float),("time",float),("proteinring",list),
                ("ligand_ring_ids",list),("distance",float),("angle",float),
                ("offset",float),("type","|U4"),("resid",int),("resname","|U4"),("segid","|U8") ]
        out = np.empty((num_records,),dtype=dtype)
        cursor=0
        for contact in self.timeseries:
            out[cursor] = (contact.frame, contact.time,contact.proteinring,contact.ligandring,contact.distance,contact.angle,contact.offset,contact.type,contact.resid,contact.resname,contact.segid)
            cursor+=1
        return out.view(np.recarray)


    def count_by_time(self):
        """Count how many pi-pi interactions occured in each frame.
        Returns numpy array."""
        out = np.empty((len(self.timesteps),), dtype=[('time', float), ('count', int)])
        for cursor,timestep in enumerate(self.timesteps):
            out[cursor] = (timestep,len([x for x in self.timeseries if x.time==timestep]))
        return out.view(np.recarray)

    def count_by_type(self):
        """Count how many times each individual pi-pi interaction occured throughout the simulation.
        Returns numpy array."""
        pistack = defaultdict(int)
        for contact in self.timeseries:
            #count by residue name not by proteinring
            pkey = (contact.ligandring,contact.type, contact.resid,contact.resname,contact.segid)
            pistack[pkey]+=1
        dtype = [("ligand_ring_ids",list),("type","|U4"),("resid",int),("resname","|U4"),("segid","|U8"),("frequency",float) ]
        out = np.empty((len(pistack),),dtype=dtype)
        tsteps = float(len(self.timesteps))
        for cursor,(key,count) in enumerate(pistack.iteritems()):
            out[cursor] = key + (count / tsteps,)
        return out.view(np.recarray)

    def get_ligand_ring_selection(self,ring):
        """MDAnalysis atom selections of aromatic rings present in the ligand molecule.
        Takes:
            * ring * - index in self.ligrings dictionary
        Output:
            * ring_selection * - MDAnalysis Atom group"""
        ring_names = ""
        for atom in self.ligrings[ring]:
            ring_names = ring_names+" "+str(atom)
        ring_selection = self.topology_data.universe.ligand.select_atoms("name "+ring_names)
        return ring_selection

    def get_pistacking_frequency(self,analysis_cutoff):
        """Calculates the frequency of pi-pi interactions throughout simulations. If the frequency exceeds the
        analysis cutoff, this interaction will be plotted in the final figure.
        Takes:
            * analysis_cutoff * - fraction of simulation time a feature has to be present for to be plotted
        Output:
            * self.pi_contacts_for_drawing * - dictionary of pi-pi interactions to be plotted """
        self.frequency = defaultdict(int)
        for traj in self.pistacking_by_type:
            for contact in self.pistacking_by_type[traj]:
                self.frequency[contact["ligand_ring_ids"],contact["type"],contact["resid"],contact["resname"],contact["segid"]]+=contact["frequency"]
        draw_frequency = {i:self.frequency[i] for i in self.frequency if self.frequency[i]>(int(len(self.trajectory))*float(analysis_cutoff))}

        self.pi_contacts_for_drawing = {}
        for contact in draw_frequency:
            self.pi_contacts_for_drawing[contact]=draw_frequency[contact]

    def write_output_files(self,traj):
        """
        The total hydrogen bond count per frame is provided as CSV output file.
        Each trajectory has a separate file.
        """
        try:
            os.chdir("analysis")
        except Exception as e:
            os.mkdir("analysis")
            os.chdir("analysis")
        os.mkdir("pistacking")
        os.chdir("pistacking")
        with open('pistacking_data_total_'+str(traj)+'.csv', 'wb') as outfile:
            hwriter = csv.writer(outfile, delimiter=' ')
            for time in self.pistacking_by_time[traj]:
                hwriter.writerow([time[0],time[1]])
        for bond in self.pistacking_by_type[traj]:
            if bond in self.pi_contacts_for_drawing.keys():
                with open("pi_contact_"+str(traj)+".csv","wb") as outfile:
                    hwriter = csv.writer(outfile, delimiter=' ')
                    for time in self.timesteps:
                        result = [1 if x[0]==time and x["acceptor_idx"]==bond["acceptor_idx"] else 0 for x in self.timeseries][0]
                        hwriter.writerow([time,result])
        os.chdir("../../")
