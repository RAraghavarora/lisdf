from abc import ABC
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from lisdf.components.base import Pose, StringConfigurable, StringifyContext
from lisdf.components.control import JointControlInfo, JointInfo
from lisdf.components.material import RGBA, Material
from lisdf.components.sensor import Sensor
from lisdf.components.shape import ShapeInfo
from lisdf.utils.printing import indent_text
from lisdf.utils.typing import Vector3f, Vector4f


@dataclass
class Inertia(StringConfigurable):
    ixx: float
    ixy: float
    ixz: float
    iyy: float
    iyz: float
    izz: float

    @classmethod
    def zeros(cls) -> "Inertia":
        return cls(0, 0, 0, 0, 0, 0)

    @classmethod
    def from_diagonal(cls, ixx, iyy, izz) -> "Inertia":
        return cls(ixx, 0, 0, iyy, 0, izz)

    @property
    def matrix(self) -> np.ndarray:
        return np.array(
            [
                [self.ixx, self.ixy, self.ixz],
                [self.ixy, self.iyy, self.iyz],
                [self.ixz, self.iyz, self.izz],
            ],
            dtype=np.float32,
        )

    def _to_sdf(self, ctx: StringifyContext) -> str:
        return f"""<inertia>
  <ixx>{self.ixx}</ixx>
  <ixy>{self.ixy}</ixy>
  <ixz>{self.ixz}</ixz>
  <iyy>{self.iyy}</iyy>
  <iyz>{self.iyz}</iyz>
  <izz>{self.izz}</izz>
</inertia>"""

    def _to_urdf(self, ctx: StringifyContext) -> str:
        return (
            f'<inertia ixx="{self.ixx}"'
            f' ixy="{self.ixy}" ixz="{self.ixz}"'
            f' iyy="{self.iyy}" iyz="{self.iyz}"'
            f' izz="{self.izz}" />'
        )


@dataclass
class Inertial(StringConfigurable):
    mass: float
    pose: Pose
    inertia: Inertia

    @classmethod
    def zeros(cls) -> "Inertial":
        return cls(0, Pose.identity(), Inertia.zeros())

    def _to_sdf(self, ctx: StringifyContext) -> str:
        return f"""<inertial>
  <mass>{self.mass}</mass>
  {self.pose.to_sdf(ctx)}
  {indent_text(self.inertia.to_sdf(ctx)).strip()}
</inertial>"""

    def _to_urdf(self, ctx: StringifyContext) -> str:
        return f"""<inertial>
  <mass value="{self.mass}"></mass>
  {self.pose.to_urdf(ctx)}
  {indent_text(self.inertia.to_urdf(ctx)).strip()}
</inertial>"""


@dataclass
class SurfaceContact(StringConfigurable):
    def _to_sdf(self, ctx: StringifyContext) -> str:
        return ""

    def _to_urdf(self, ctx: StringifyContext) -> str:
        return ""


@dataclass
class SurfaceFriction(StringConfigurable):
    def _to_sdf(self, ctx: StringifyContext) -> str:
        return ""

    def _to_urdf(self, ctx: StringifyContext) -> str:
        return ""


@dataclass
class SurfaceInfo(StringConfigurable):
    contact: Optional[SurfaceContact] = None
    friction: Optional[SurfaceFriction] = None

    def _to_sdf(self, ctx: StringifyContext) -> str:
        return f"""<surface>
  {indent_text(self.contact.to_sdf(ctx)).strip() if self.contact else ""}
  {indent_text(self.friction.to_sdf(ctx)).strip() if self.friction else ""}
</surface>"""

    def _to_urdf(self, ctx: StringifyContext) -> str:
        ctx.warning(self, "Link surface properties are not supported in URDF.")
        return ""


@dataclass
class _Geom(StringConfigurable, ABC):
    """Shared base class for collision and visual."""

    name: str
    pose: Pose
    shape: ShapeInfo


@dataclass
class Collision(_Geom):
    surface: Optional[SurfaceInfo] = None

    @property
    def type(self):
        return self.shape.type

    def _to_sdf(self, ctx: StringifyContext) -> str:
        return f"""<collision name="{self.name}">>
  {self.pose.to_sdf(ctx) if self.pose is not None else ""}
  <geometry>
    {indent_text(self.shape.to_sdf(ctx), 2).strip()}
  </geometry>
  {indent_text(self.surface.to_sdf(ctx)).strip() if self.surface is not None else ""}
</collision>"""

    def _to_urdf(self, ctx: StringifyContext) -> str:
        name = ctx.get_scoped_name(self.name)
        return f"""<collision name="{name}">
  {self.pose.to_urdf(ctx)}
  <geometry>
    {indent_text(self.shape.to_urdf(ctx), 2).strip()}
  </geometry>
  {indent_text(self.surface.to_urdf(ctx)).strip() if self.surface is not None else ""}
</collision>"""


@dataclass
class Visual(_Geom):
    material: Optional[Material] = None

    @property
    def type(self):
        return self.shape.type

    def _to_sdf(self, ctx: StringifyContext) -> str:
        return f"""<visual name="{self.name}">
  {self.pose.to_sdf(ctx) if self.pose is not None else ""}
  <geometry>
    {indent_text(self.shape.to_sdf(ctx), 2).strip()}
  </geometry>
  {indent_text(self.material.to_sdf(ctx)).strip() if self.material is not None else ""}
</visual>"""

    def _to_material_urdf(self, ctx: StringifyContext) -> str:
        name = ctx.get_scoped_name(self.name)
        if self.material is not None:
            return f"""<material name="{name}_material">
  {indent_text(self.material.to_urdf(ctx)).strip() if self.material is not None else ""}
</material>"""
        return ""

    def _to_urdf(self, ctx: StringifyContext) -> str:
        name = ctx.get_scoped_name(self.name)
        material_str = ""
        if self.material is not None:
            material_str = self._to_material_urdf(ctx)

        return f"""<visual name="{name}">
  {self.pose.to_urdf(ctx)}
  <geometry>
    {indent_text(self.shape.to_urdf(ctx), 2).strip()}
  </geometry>
  {indent_text(material_str).strip()}
</visual>"""


@dataclass
class Link(StringConfigurable):
    name: str
    parent: Optional[str]
    pose: Optional[Pose]
    inertial: Optional[Inertial] = None
    collisions: List[Collision] = field(default_factory=list)
    visuals: List[Visual] = field(default_factory=list)
    sensors: List[Sensor] = field(default_factory=list)

    @classmethod
    def from_simple_geom(
        cls,
        name: str,
        pose: Pose,
        shape_type: str,
        rgba: Vector4f,
        inertial: Optional[Inertial] = None,
        **kwargs,
    ):
        if inertial is None:
            inertial = Inertial.zeros()
        shape = ShapeInfo.from_type(shape_type, **kwargs)
        material = RGBA(*rgba)
        return cls(
            name,
            pose=None,
            parent=None,
            inertial=inertial,
            collisions=[Collision(name + "_collision", pose, shape)],
            visuals=[Visual(name + "_visual", pose, shape, material)],
        )

    def _to_sdf(self, ctx: StringifyContext) -> str:
        collision_str = "\n".join([c.to_sdf(ctx) for c in self.collisions])
        visual_str = "\n".join([v.to_sdf(ctx) for v in self.visuals])
        return f"""<link name="{self.name}">
  {self.pose.to_sdf(ctx) if self.pose is not None else ""}
  {indent_text(self.inertial.to_sdf(ctx)).strip() if self.inertial is not None else ""}
  {indent_text(collision_str).strip()}
  {indent_text(visual_str).strip()}
</link>"""

    def _to_urdf(self, ctx: StringifyContext) -> str:
        if self.pose is not None:
            ctx.push_scoped_pose(self.pose)

        try:
            name = ctx.get_scoped_name(self.name)
            collision_str = "\n".join([c.to_urdf(ctx) for c in self.collisions])
            visual_str = "\n".join([v.to_urdf(ctx) for v in self.visuals])

            return f"""<link name="{name}">
  {indent_text(self.inertial.to_urdf(ctx)).strip() if self.inertial is not None else ""}
  {indent_text(collision_str).strip()}
  {indent_text(visual_str).strip()}
</link>"""
        finally:
            ctx.pop_scoped_pose()

    def to_sdf_xml(self) -> str:
        model = Model(self.name)
        model.links.append(self)
        return model.to_sdf_xml()

    def to_urdf_xml(self) -> str:
        model = Model(self.name)
        model.links.append(self)
        return model.to_urdf_xml()


@dataclass
class Joint(StringConfigurable):
    name: str
    parent: str
    child: str
    pose: Pose
    joint_info: JointInfo
    control_info: Optional[JointControlInfo] = None

    @property
    def type(self):
        return self.joint_info.type

    # TODO(Jiayuan Mao @ 03/24): add a link to the corresponding `model`,
    # so we can use joint.parent_link to access the corresponding link
    # object.

    def _to_sdf(self, ctx: StringifyContext) -> str:
        name_str = f' name="{self.name}"' if self.name is not None else ""
        return f"""<joint{name_str} type="{self.type}">
  <parent>{self.parent}</parent>
  <child>{self.child}</child>
  {self.pose.to_sdf(ctx)}
  {indent_text(self.joint_info.to_sdf(ctx)).strip()}
  {indent_text(self.control_info.to_sdf(ctx)).strip()
  if self.control_info is not None else ""}
</joint>"""

    def _to_urdf(self, ctx: StringifyContext) -> str:
        assert self.name is not None
        name = ctx.get_scoped_name(self.name)
        parent = ctx.get_scoped_name(self.parent)
        child = ctx.get_scoped_name(self.child)
        return f"""<joint name="{name}" type="{self.type}">
  <parent link="{parent}"/>
  <child link="{child}"/>
  {self.pose.to_urdf(ctx)}
  {indent_text(self.joint_info.to_urdf(ctx)).strip()}
  {indent_text(self.control_info.to_urdf(ctx)).strip()
  if self.control_info is not None else ""}
</joint>"""


@dataclass
class Model(StringConfigurable):
    name: str
    pose: Optional[Pose] = None
    parent: Optional[str] = None
    static: bool = False

    links: List[Link] = field(default_factory=list)
    joints: List[Joint] = field(default_factory=list)

    def _to_sdf(self, ctx: StringifyContext) -> str:
        link_str = "\n".join([link.to_sdf(ctx) for link in self.links])
        joint_str = "\n".join([joint.to_sdf(ctx) for joint in self.joints])
        return f"""<model name="{self.name}">
  <static>{self.static}</static>
  {self.pose.to_sdf(ctx) if self.pose is not None else ""}
  {indent_text(link_str).strip()}
  {indent_text(joint_str).strip()}
</model>"""

    def to_sdf_xml(self) -> str:
        return f"""<?xml version="1.0"?>
<sdf version="1.9">
{self.to_sdf()}
</sdf>"""

    def _to_urdf(self, ctx: StringifyContext) -> str:
        if self.pose is not None:
            ctx.warning(self, "Model::pose will be ignored in URDF.")
        if self.parent is not None:
            ctx.warning(self, "Model::parent will be ignored in URDF.")
        if self.static:
            ctx.warning(self, "Model::static will be ignored in URDF.")

        ctx.push_scoped_name(self.name)
        try:
            link_str = "\n".join([link.to_urdf(ctx) for link in self.links])
            joint_str = "\n".join([joint.to_urdf(ctx) for joint in self.joints])
            return f"""<robot name="{self.name}">
  {indent_text(link_str).strip()}
  {indent_text(joint_str).strip()}
</robot>"""
        finally:
            ctx.pop_scoped_name()

    def to_urdf_xml(self) -> str:
        return f"""<?xml version="1.0"?>
{self.to_urdf()}"""


@dataclass
class SDFInclude(StringConfigurable):
    name: Optional[str]
    uri: str
    scale: Vector3f
    pose: Optional[Pose]
    parent: Optional[str] = None
    static: bool = False

    _scale1d: Optional[float] = None
    _content: Optional[StringConfigurable] = None

    @property
    def scale_1d(self):
        assert self._scale1d is not None, "scale_1d is not allowed. Use scale instead."
        return self._scale1d

    @property
    def content(self):
        assert self._content is not None, "content has not been parsed."
        return self._content

    def _to_sdf(self, ctx: StringifyContext) -> str:
        if self._scale1d is not None:
            scale_str = f"<scale>{self._scale1d}</scale>"
        else:
            scale_str = (
                f"<scale>{self.scale[0]} {self.scale[1]} {self.scale[2]}</scale>"
            )
        name_str = f' name="{self.name}"' if self.name is not None else ""
        return f"""<include{name_str}">
  <uri>{self.uri}</uri>
  <static>{self.static}</static>
  {scale_str}
  {self.pose.to_sdf(ctx) if self.pose is not None else ""}
</include>"""

    def _to_urdf(self, ctx: StringifyContext) -> str:
        raise ValueError("Include tags is not supported for URDF.")


@dataclass
class URDFInclude(SDFInclude):
    pass
