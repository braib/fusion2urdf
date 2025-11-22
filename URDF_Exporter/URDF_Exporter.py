#Author-syuntoku14
#Description-Generate URDF file from Fusion 360
#Modified to handle Fusion 360 versioned component names and duplicate names

import adsk, adsk.core, adsk.fusion, traceback
import os
import sys

# Add the path to import NameManager
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from .utils import utils
from .core import Link, Joint, Write

# Import or define NameManager
try:
    from .utils.name_manager import NameManager
except:
    # If import fails, define it inline
    import re
    
    class NameManager:
        def __init__(self):
            self.link_name_map = {}
            self.link_name_counts = {}
            self.used_names = set()
            
        def clean_name(self, name):
            cleaned = name.replace(',', '')
            cleaned = re.sub('[ :()]', '_', cleaned)
            cleaned = re.sub('_+', '_', cleaned)
            cleaned = cleaned.strip('_')
            return cleaned
        
        def get_unique_link_name(self, occurrence_name, component_name):
            if occurrence_name in self.link_name_map:
                return self.link_name_map[occurrence_name]
            
            base_name = self.clean_name(component_name)
            
            if base_name.lower() == 'base_link':
                unique_name = 'base_link'
                if unique_name not in self.used_names:
                    self.link_name_map[occurrence_name] = unique_name
                    self.used_names.add(unique_name)
                    return unique_name
            
            if base_name in self.link_name_counts:
                self.link_name_counts[base_name] += 1
                unique_name = f"{base_name}_{self.link_name_counts[base_name]}"
            else:
                if base_name in self.used_names:
                    self.link_name_counts[base_name] = 1
                    unique_name = f"{base_name}_1"
                else:
                    self.link_name_counts[base_name] = 0
                    unique_name = base_name
            
            self.link_name_map[occurrence_name] = unique_name
            self.used_names.add(unique_name)
            return unique_name
        
        def get_link_name_for_occurrence(self, occurrence_name):
            return self.link_name_map.get(occurrence_name)
        
        def get_unique_joint_name(self, joint_name):
            return self.clean_name(joint_name)
        
        def print_mapping(self):
            print("\n=== Link Name Mapping ===")
            for original, unique in sorted(self.link_name_map.items()):
                if original != unique:
                    print(f"{original} -> {unique}")
            print("========================\n")

"""
# length unit is 'cm' and inertial unit is 'kg/cm^2'
# If there is no 'body' in the root component, maybe the coordinates are wrong.
"""

# joint effort: 100
# joint velocity: 100
# supports "Revolute", "Rigid" and "Slider" joint types

def run(context):
    ui = None
    success_msg = 'Successfully create URDF file'
    msg = success_msg
    
    try:
        # --------------------
        # initialize
        app = adsk.core.Application.get()
        ui = app.userInterface
        product = app.activeProduct
        design = adsk.fusion.Design.cast(product)
        title = 'Fusion2URDF'
        
        if not design:
            ui.messageBox('No active Fusion design', title)
            return
        
        root = design.rootComponent  # root component 
        components = design.allComponents
        
        # Initialize NameManager for handling duplicate names
        name_manager = NameManager()
        
        # set the names        
        robot_name = root.name.split()[0]
        package_name = robot_name + '_description'
        save_dir = utils.file_dialog(ui)
        
        if save_dir == False:
            ui.messageBox('Fusion2URDF was canceled', title)
            return 0
        
        save_dir = save_dir + '/' + package_name
        try: 
            os.mkdir(save_dir)
        except: 
            pass     
        
        package_dir = os.path.abspath(os.path.dirname(__file__)) + '/package/'
        
        # --------------------
        # set dictionaries
        
        # Generate inertial_dict first to populate name_manager
        inertial_dict, msg = Link.make_inertial_dict(root, msg, name_manager)
        if msg != success_msg:
            ui.messageBox(msg, title)
            return 0
        
        # Check if base_link exists (with version handling)
        has_base_link = 'base_link' in inertial_dict
        
        if not has_base_link:
            # Try to find any component that starts with "base_link"
            base_link_candidates = [key for key in inertial_dict.keys() 
                                   if key.lower().startswith('base_link')]
            
            if base_link_candidates:
                msg = f'Found component "{base_link_candidates[0]}" but it should be named exactly "base_link" (without version numbers).\n\n'
                msg += 'The exporter has automatically handled this, but please rename your component to "base_link" in Fusion 360 for clarity.'
                ui.messageBox(msg, title)
            else:
                msg = 'There is no base_link component found.\n\n'
                msg += 'Please create a component named "base_link" and run again.\n'
                msg += 'Note: The component name should start with "base_link" (case insensitive).'
                ui.messageBox(msg, title)
                return 0
        
        # Generate joints_dict using the populated name_manager
        joints_dict, msg = Joint.make_joints_dict(root, msg, name_manager)
        if msg != success_msg:
            ui.messageBox(msg, title)
            return 0   
        
        # Print name mapping for debugging
        name_manager.print_mapping()
        
        links_xyz_dict = {}
        
        # --------------------
        # Generate URDF
        Write.write_urdf(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir)
        Write.write_materials_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir)
        Write.write_transmissions_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir)
        Write.write_gazebo_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir)
        Write.write_display_launch(package_name, robot_name, save_dir)
        Write.write_gazebo_launch(package_name, robot_name, save_dir)
        Write.write_control_launch(package_name, robot_name, save_dir, joints_dict)
        Write.write_yaml(package_name, robot_name, save_dir, joints_dict)
        
        # copy over package files
        utils.copy_package(save_dir, package_dir)
        utils.update_cmakelists(save_dir, package_name)
        utils.update_package_xml(save_dir, package_name)
        
        # Generate STL files with unique names
        utils.copy_occs(root, name_manager)
        utils.export_stl(design, save_dir, components, name_manager)   
        
        ui.messageBox(msg, title)
        
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))