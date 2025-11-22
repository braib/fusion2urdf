# -*- coding: utf-8 -*-
"""
Name manager to handle duplicate names and ensure uniqueness
"""

import re

class NameManager:
    """
    Manages unique names for links and joints, handling duplicates
    """
    def __init__(self):
        self.link_name_map = {}  # Maps original occurrence names to unique clean names
        self.link_name_counts = {}  # Tracks count of each base name
        self.used_names = set()  # Set of all used names
        self.component_to_mesh = {}  # Maps component names to mesh filenames
        
    def clean_name(self, name):
        """
        Clean a name by removing/replacing invalid characters
        - Remove commas
        - Replace spaces, colons, parentheses with underscores
        - Remove multiple consecutive underscores
        - Convert to lowercase
        """
        # Remove commas first
        cleaned = name.replace(',', '')
        # Replace spaces, colons, parentheses with underscores
        cleaned = re.sub('[ :()]', '_', cleaned)
        # Remove multiple consecutive underscores
        cleaned = re.sub('_+', '_', cleaned)
        # Remove leading/trailing underscores
        cleaned = cleaned.strip('_')
        # Convert to lowercase
        cleaned = cleaned.lower()
        return cleaned
    
    def get_mesh_filename(self, component_name):
        """
        Get the mesh filename for a component (without uniqueness suffix)
        This is used for STL export and mesh references
        
        Parameters
        ----------
        component_name : str
            The component name from Fusion 360
            
        Returns
        -------
        str
            Cleaned name for mesh file (lowercase, no suffix)
        """
        if component_name in self.component_to_mesh:
            return self.component_to_mesh[component_name]
        
        # Clean and store
        mesh_name = self.clean_name(component_name)
        
        # Special case for base_link
        if mesh_name == 'base_link':
            self.component_to_mesh[component_name] = 'base_link'
            return 'base_link'
        
        self.component_to_mesh[component_name] = mesh_name
        return mesh_name
    
    def get_unique_link_name(self, occurrence_name, component_name):
        """
        Get a unique name for a link based on occurrence name
        If the name already exists, append _1, _2, etc.
        
        Parameters
        ----------
        occurrence_name : str
            The full occurrence name from Fusion 360
        component_name : str
            The component name
            
        Returns
        -------
        str
            Unique cleaned name for this link (lowercase)
        """
        # Check if we already processed this exact occurrence
        if occurrence_name in self.link_name_map:
            return self.link_name_map[occurrence_name]
        
        # Clean the component name
        base_name = self.clean_name(component_name)
        
        # Special handling for base_link
        if base_name == 'base_link':
            unique_name = 'base_link'
            if unique_name not in self.used_names:
                self.link_name_map[occurrence_name] = unique_name
                self.used_names.add(unique_name)
                return unique_name
        
        # Check if this base name has been used before
        if base_name in self.link_name_counts:
            # Increment counter and create unique name
            self.link_name_counts[base_name] += 1
            unique_name = f"{base_name}_{self.link_name_counts[base_name]}"
        else:
            # First time seeing this base name
            if base_name in self.used_names:
                # The base name itself is already used, start with _1
                self.link_name_counts[base_name] = 1
                unique_name = f"{base_name}_1"
            else:
                # Use the base name as is
                self.link_name_counts[base_name] = 0
                unique_name = base_name
        
        # Store the mapping and mark as used
        self.link_name_map[occurrence_name] = unique_name
        self.used_names.add(unique_name)
        
        return unique_name
    
    def get_link_name_for_occurrence(self, occurrence_name):
        """
        Retrieve the unique link name for a given occurrence
        
        Parameters
        ----------
        occurrence_name : str
            The occurrence name to look up
            
        Returns
        -------
        str
            The unique link name, or None if not found
        """
        return self.link_name_map.get(occurrence_name)
    
    def get_unique_joint_name(self, joint_name):
        """
        Get a unique name for a joint (lowercase)
        
        Parameters
        ----------
        joint_name : str
            Original joint name
            
        Returns
        -------
        str
            Cleaned joint name (lowercase)
        """
        return self.clean_name(joint_name)
    
    def print_mapping(self):
        """
        Print the name mapping for debugging
        """
        print("\n=== Link Name Mapping ===")
        print("Occurrence -> Unique Link Name | Mesh Filename")
        for original, unique in sorted(self.link_name_map.items()):
            print(f"{original} -> {unique}")
        print("\n=== Component to Mesh Mapping ===")
        for comp, mesh in sorted(self.component_to_mesh.items()):
            print(f"{comp} -> {mesh}.stl")
        print("========================\n")