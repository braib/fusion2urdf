# -*- coding: utf-8 -*-
"""
Created on Sun May 12 19:15:34 2019

@author: syuntoku
Modified to handle Fusion 360 versioned component names
"""

import adsk, adsk.core, adsk.fusion
import os.path, re
from xml.etree import ElementTree
from xml.dom import minidom
import shutil
import fileinput
import sys


def is_base_link(component_name):
    """
    Check if a component name represents the base_link
    Handles Fusion 360's version numbering (e.g., "base_link v1", "base_link v2")
    
    Parameters
    ----------
    component_name: str
        The component name to check
        
    Returns
    -------
    bool
        True if this is a base_link component
    """
    # Remove version numbers and whitespace, convert to lowercase for comparison
    clean_name = component_name.split()[0].lower()
    return clean_name == 'base_link'


def copy_occs(root, name_manager=None):    
    """    
    duplicate all the components - creates new clean copies for STL export
    
    Parameters
    ----------
    root: adsk.fusion.Design.cast(product)
        Root component
    name_manager: NameManager
        Manager for handling unique names
    """    
    allOccs = root.occurrences
    
    # Store original occurrence info before making changes
    occ_info_list = []
    for i in range(allOccs.count):
        occs = allOccs.item(i)
        if occs.bRepBodies.count > 0:
            # Get unique name from name manager
            if name_manager:
                unique_name = name_manager.get_unique_link_name(occs.name, occs.component.name)
            else:
                unique_name = re.sub('[ :(),]', '_', occs.component.name)
                unique_name = re.sub('_+', '_', unique_name).strip('_')
            
            occ_info = {
                'occurrence': occs,
                'component': occs.component,
                'name': occs.name,
                'unique_name': unique_name,
                'is_base_link': is_base_link(occs.component.name)
            }
            occ_info_list.append(occ_info)
    
    # Create new occurrences from the stored info
    created_occs = []
    for occ_info in occ_info_list:
        try:
            occs = occ_info['occurrence']
            transform = adsk.core.Matrix3D.create()
            
            # Create new occurrence
            new_occs = allOccs.addNewComponent(transform)
            
            # Set the new component name
            if occ_info['is_base_link']:
                new_occs.component.name = 'base_link'
            else:
                new_occs.component.name = occ_info['unique_name']
            
            # Get the newly created occurrence
            new_occs = allOccs.item(allOccs.count - 1)
            
            # Copy bodies from original component to new component
            source_bodies = occ_info['component'].bRepBodies
            for j in range(source_bodies.count):
                body = source_bodies.item(j)
                try:
                    body.copyToComponent(new_occs)
                except RuntimeError as e:
                    # Sometimes direct copy fails, try alternative approach
                    print(f'Warning: Could not copy body {j} from {occ_info["name"]}: {str(e)}')
                    continue
            
            created_occs.append(new_occs)
            
        except Exception as e:
            print(f'Warning: Could not process occurrence {occ_info["name"]}: {str(e)}')
            continue
    
    # Rename original components (mark as old) - skip root component
    for occ_info in occ_info_list:
        try:
            comp = occ_info['component']
            # Don't rename root component
            if comp != root:
                comp.name = 'old_component'
        except Exception as e:
            # Skip if we can't rename
            print(f'Warning: Could not rename component {occ_info["name"]}: {str(e)}')
            continue


def export_stl(design, save_dir, components, name_manager=None):  
    """
    export stl files into "save_dir/"
    
    Parameters
    ----------
    design: adsk.fusion.Design.cast(product)
    save_dir: str
        directory path to save
    components: design.allComponents
    name_manager: NameManager
        Manager for handling unique names
    """
          
    # create a single exportManager instance
    exportMgr = design.exportManager
    # get the script location
    try: os.mkdir(save_dir + '/meshes')
    except: pass
    scriptDir = save_dir + '/meshes'  
    
    # Track which meshes we've already exported
    exported_meshes = set()
    
    # export the occurrence one by one in the component to a specified file
    for component in components:
        allOccus = component.allOccurrences
        for occ in allOccus:
            if 'old_component' not in occ.component.name:
                try:
                    # Get mesh filename (without uniqueness suffix, lowercase)
                    if name_manager:
                        mesh_filename = name_manager.get_mesh_filename(occ.component.name)
                    else:
                        # Clean the component name: remove commas, replace spaces and special characters with underscores, lowercase
                        mesh_filename = occ.component.name.replace(',', '')
                        mesh_filename = re.sub('[ :()]', '_', mesh_filename)
                        mesh_filename = re.sub('_+', '_', mesh_filename).strip('_')
                        mesh_filename = mesh_filename.lower()
                    
                    # Only export each unique mesh once
                    if mesh_filename in exported_meshes:
                        print(f'Skipping duplicate: {mesh_filename} (already exported)')
                        continue
                    
                    print(f'Exporting: {mesh_filename}.stl')
                    fileName = scriptDir + "/" + mesh_filename
                    
                    # create stl exportOptions
                    stlExportOptions = exportMgr.createSTLExportOptions(occ, fileName)
                    stlExportOptions.sendToPrintUtility = False
                    stlExportOptions.isBinaryFormat = True
                    # options are .MeshRefinementLow .MeshRefinementMedium .MeshRefinementHigh
                    stlExportOptions.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementLow
                    exportMgr.execute(stlExportOptions)
                    
                    exported_meshes.add(mesh_filename)
                    
                except Exception as e:
                    print('Component ' + occ.component.name + ' has something wrong: ' + str(e))



def file_dialog(ui):     
    """
    display the dialog to save the file
    """
    # Set styles of folder dialog.
    folderDlg = ui.createFolderDialog()
    folderDlg.title = 'Fusion Folder Dialog' 
    
    # Show folder dialog
    dlgResult = folderDlg.showDialog()
    if dlgResult == adsk.core.DialogResults.DialogOK:
        return folderDlg.folder
    return False


def origin2center_of_mass(inertia, center_of_mass, mass):
    """
    convert the moment of the inertia about the world coordinate into 
    that about center of mass coordinate

    Parameters
    ----------
    moment of inertia about the world coordinate:  [xx, yy, zz, xy, yz, xz]
    center_of_mass: [x, y, z]
    
    Returns
    ----------
    moment of inertia about center of mass : [xx, yy, zz, xy, yz, xz]
    """
    x = center_of_mass[0]
    y = center_of_mass[1]
    z = center_of_mass[2]
    translation_matrix = [y**2 + z**2, x**2 + z**2, x**2 + y**2,
                         -x*y, -y*z, -x*z]
    return [round(i - mass*t, 6) for i, t in zip(inertia, translation_matrix)]


def prettify(elem):
    """
    Return a pretty-printed XML string for the Element.
    
    Parameters
    ----------
    elem : xml.etree.ElementTree.Element
    
    Returns
    ----------
    pretified xml : str
    """
    rough_string = ElementTree.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def copy_package(save_dir, package_dir):
    try:
        # Check if the target directory exists, if not, create it
        if not os.path.exists(save_dir + '/launch'):
            os.mkdir(save_dir + '/launch')
        if not os.path.exists(save_dir + '/urdf'):
            os.mkdir(save_dir + '/urdf')
        
        # Check if the package directory exists and copy it
        if os.path.exists(package_dir):
            shutil.copytree(package_dir, save_dir, dirs_exist_ok=True)
        else:
            print(f"Package directory '{package_dir}' does not exist.")
        
    except Exception as e:
        print(f"Error copying package: {e}")


def update_cmakelists(save_dir, package_name):
    file_name = save_dir + '/CMakeLists.txt'

    for line in fileinput.input(file_name, inplace=True):
        if 'project(fusion2urdf)' in line:
            sys.stdout.write("project(" + package_name + ")\n")
        else:
            sys.stdout.write(line)


def update_package_xml(save_dir, package_name):
    file_name = save_dir + '/package.xml'

    for line in fileinput.input(file_name, inplace=True):
        if '<name>' in line:
            sys.stdout.write("  <name>" + package_name + "</name>\n")
        elif '<description>' in line:
            sys.stdout.write("<description>The " + package_name + " package</description>\n")
        else:
            sys.stdout.write(line)