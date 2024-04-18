# This code is part of KQCircuits
# Copyright (C) 2024 IQM Finland Oy
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with this program. If not, see
# https://www.gnu.org/licenses/gpl-3.0.html.
#
# The software distribution should follow IQM trademark policy for open-source software
# (meetiqm.com/iqm-open-source-trademark-policy). IQM welcomes contributions to the code.
# Please see our contribution agreements for individuals (meetiqm.com/iqm-individual-contributor-license-agreement)
# and organizations (meetiqm.com/iqm-organization-contributor-license-agreement).

import logging
import sys
from pathlib import Path

from kqcircuits.pya_resolver import pya
from kqcircuits.elements.circular_capacitor import CircularCapacitor
from kqcircuits.simulations.post_process import PostProcess
from kqcircuits.simulations.single_element_simulation import get_single_element_sim_class
from kqcircuits.simulations.export.simulation_export import cross_sweep_simulation, export_simulation_oas, cross_combine
from kqcircuits.util.export_helper import (
    create_or_empty_tmp_directory,
    get_active_or_new_layout,
    open_with_klayout_or_default_application,
)
from kqcircuits.simulations.export.elmer.elmer_export import export_elmer
from kqcircuits.simulations.export.xsection.epr_correction_export import get_epr_correction_simulations
from kqcircuits.simulations.export.elmer.elmer_solution import ElmerEPR3DSolution
from kqcircuits.simulations.epr.circular_capacitor import partition_regions, correction_cuts

sim_class = get_single_element_sim_class(
    CircularCapacitor, partition_region_function=partition_regions
)  # pylint: disable=invalid-name

flip_chip = False
etch_opposite_face = False
var_str = ("_f" if flip_chip else "") + ("e" if etch_opposite_face else "")


ground_gap = 20
# If False the waveguides connected to the element will extend to the boundary of
# simulation box
use_internal_ports = False
# Only applicable if use_internal_ports =True
# Choose whether a piece of waveguide is added to the ports or not
# Only a small ground "wire" is produced that is 10um separated from the island
include_waveguides = True

wg_len = -ground_gap if use_internal_ports and not include_waveguides else 100

# Simulation parameters
sim_parameters = {
    "name": "circular_capacitor_epr" + var_str,
    "use_internal_ports": use_internal_ports,
    "use_ports": True,
    "box": pya.DBox(pya.DPoint(0, 0), pya.DPoint(600, 600)),
    "port_size": 200,
    "face_stack": ["1t1", "2b1"] if flip_chip else ["1t1"],
    "etch_opposite_face": etch_opposite_face,
    "chip_distance": 8,
    "ground_gap": ground_gap,
    "waveguide_length": wg_len,
    # This has the same effect as increasing the waveguide_length but parametrizes the total size of the element
    # "fixed_length": 500,
    "r_inner": 30,
    "r_outer": 120,
    "swept_angle": 180,
    "outer_island_width": 40,
    "a": 10,
    "b": 6,
    "a2": 10,
    "b2": 6,
    "tls_sheet_approximation": True,
    "metal_height": [0.2],  # Required for the TLS sheets to be generated
    "detach_tls_sheets_from_body": False,
    "n": 64,  # Rougher shapes make the meshing more efficient
    "vertical_over_etching": 0.050,  # Use a small vertical over etching (substrate trench)
}


solution = ElmerEPR3DSolution(
    mesh_size={
        # Note that the signal name in the mesh size definition doesn't match the one in oas/simulation layers
        # This is intended and applies the mesh refinement on all signals on the face regardless of their layer
        "1t1_gap&1t1_signal": [2.0, 2.0, 0.5],
        "1t1_gap&1t1_ground": [2.0, 2.0, 0.5],
        "2b1_gap&2b1_ground": [2.0, 2.0, 0.5],
        "optimize": {},
    },
    linear_system_method="mg",
)

# Prepare output directory
dir_path = create_or_empty_tmp_directory(Path(__file__).stem + var_str + "_output")

# Get layout
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
layout = get_active_or_new_layout()

# Cross sweep number of fingers and finger length
simulations = []
simulations += cross_sweep_simulation(
    layout,
    sim_class,
    sim_parameters,
    {
        "swept_angle": [
            30,
            120,
            180,
            270,
            300,
            320,
            330,
            340,
            350,
        ],
    },
)

pp = [PostProcess("elmer_profiler.py"), PostProcess("epr.sh", command="sh", folder="")]

simulations = cross_combine(simulations, solution)

workflow = {
    "run_gmsh_gui": False,
    "run_elmergrid": True,
    "run_elmer": True,
    "run_paraview": False,
    "python_executable": "python",
    "gmsh_n_threads": -1,  #  Number of omp threads in gmsh
    "elmer_n_processes": -1,  # Number of dependent processes (tasks) in elmer
    "elmer_n_threads": 1,  # Number of omp threads per process in elmer
}
export_elmer(simulations, path=dir_path, workflow=workflow, post_process=pp)

correction_simulations, post_process = get_epr_correction_simulations(
    simulations, dir_path, correction_cuts, metal_height=0.2
)

export_elmer(
    correction_simulations,
    dir_path,
    file_prefix="epr",
    post_process=post_process + [PostProcess("produce_cmatrix_table.py")],
)
open_with_klayout_or_default_application(export_simulation_oas(correction_simulations, dir_path, "epr"))
# Write and open oas file
open_with_klayout_or_default_application(export_simulation_oas(simulations, dir_path))