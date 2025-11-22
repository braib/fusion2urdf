#Author-syuntoku14
#Description-Generate URDF file from Fusion 360
#Modified to handle Fusion 360 versioned component names

import adsk, adsk.core, adsk.fusion, traceback
import os
import sys
from .utils import utils
from .core import Link, Joint, Write

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
        
        # Generate joints_dict. All joints are related to root. 
        joints_dict, msg = Joint.make_joints_dict(root, msg)
        if msg != success_msg:
            ui.messageBox(msg, title)
            return 0   
        
        # Generate inertial_dict
        inertial_dict, msg = Link.make_inertial_dict(root, msg)
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
        
        # Generate STL files        
        utils.copy_occs(root)
        utils.export_stl(design, save_dir, components)   
        
        ui.messageBox(msg, title)
        
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))