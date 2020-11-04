# Copyright (c) 2019-2020 IQM Finland Oy.
#
# All rights reserved. Confidential and proprietary.
#
# Distribution or reproduction of any information contained herein is prohibited without IQM Finland Oy’s prior
# written permission.

import math

from kqcircuits.pya_resolver import pya

from kqcircuits.elements.element import Element
from kqcircuits.elements.waveguide_coplanar import WaveguideCoplanar


class Meander(Element):
    """The PCell declaration for a meandering waveguide.

    Defined by two points, total length and number of meanders. Uses the same bending radius as the underling waveguide.
    """

    # TODO Remove coordinates from PCell parameters.
    PARAMETERS_SCHEMA = {
        "start": {
            "type": pya.PCellParameterDeclaration.TypeShape,
            "description": "Start",
            "default": pya.DPoint(0, 0)
        },
        "end": {
            "type": pya.PCellParameterDeclaration.TypeShape,
            "description": "End",
            "default": pya.DPoint(200, 0)
        },
        "length": {
            "type": pya.PCellParameterDeclaration.TypeDouble,
            "description": "Length [μm]",
            "default": 400
        },
        "meanders": {
            "type": pya.PCellParameterDeclaration.TypeInt,
            "description": "Number of meanders (at least 2)",
            "default": 3
        }
    }

    def coerce_parameters_impl(self):
        self.meanders = max(self.meanders, 2)

    def can_create_from_shape_impl(self):
        return self.shape.is_path()

    def parameters_from_shape_impl(self):
        points = [pya.DPoint(point * self.layout.dbu) for point in self.shape.each_point()]
        self.start = points[0]
        self.end = points[-1]

    def produce_impl(self):
        points = [pya.DPoint(0, 0)]
        l_direct = self.start.distance(self.end)
        l_rest = l_direct - self.meanders * 2 * self.r
        l_single_meander = (l_direct - self.length + self.meanders * (math.pi - 4) * self.r) / (2 - 2 * self.meanders)
        l_single_meander = (self.length - (l_rest - 2 * self.r) - (self.meanders * 2 + 2) * (math.pi / 2) * self.r - (
                    self.meanders - 1) * self.r * 2) / (2 * self.meanders)

        points.append(pya.DPoint(l_rest / 2, 0))
        for i in range(self.meanders):
            points.append(pya.DPoint(l_rest / 2 + i * 2 * self.r, ((-1) ** (i % 2)) * (l_single_meander + 2 * self.r)))
            points.append(
                pya.DPoint(l_rest / 2 + (i + 1) * 2 * self.r, ((-1) ** (i % 2)) * (l_single_meander + 2 * self.r)))
        points.append(pya.DPoint(l_direct - l_rest / 2, 0))
        points.append(pya.DPoint(l_direct, 0))
        # print(set(points))
        waveguide = self.add_element(WaveguideCoplanar,
            path=pya.DPath(points, 1.),
            r=self.r,
            face_ids=self.face_ids,
            n=self.n
        )

        angle = 180 / math.pi * math.atan2(self.end.y - self.start.y, self.end.x - self.start.x)
        transf = pya.DCplxTrans(1, angle, False, pya.DVector(self.start))
        self.insert_cell(waveguide, transf)
