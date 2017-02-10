# (C) Copyright 2016 Vit Mojzis, vmojzis@redhat.com
# 
# This program is distributed under the terms of the GNU General Public License
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

#sys.path.append(egg_path)
import networkx as nx
import matplotlib.pyplot as plt

import selinux
import sepolicy   
import bisect
import sys
import copy
import sepolicyanalysis.policy_data_collection as data
import sepolicyanalysis.policy_parser as pparse

#Represents group of selinux types defined in the same package
#domains - set of types with attrinbute "domain"
#resources - non-domain types
#Contains only type names (not the actual "type" object)! 
class DomainGroup(object):
	"""
	Query the RBAC rules.

	Parameter:
	policy            The policy to query.

	Keyword Parameters/Class attributes:

	Instance attributes:

	name 			Group name
	domain 			Set of domains in the group
	resources 		Set of resources belonging to the group
	types 			Set of all types in the group
	"""

	def __init__(self, name):
		self.name = name
		self.domains = set()
		self.resources = set()

	def __hash__(self):
		return hash(self.name)

	def __eq__(self, other):
		if isinstance(other, DomainGroup):
			return self.name == other.name
		else:
			return False

	def __str__(self):
		return self.name

	'''def __repr__(self):
		#<domain_grouping.DomainGroup object at 0x7f67113ab390
		return ("<" + self.__class__.__name__ + " object at " + hex(id(self)) + " " + self.name + ">")
	'''
	def __repr__(self):
		#<domain_grouping.DomainGroup object at 0x7f67113ab390
		return (self.name)

	def content_str(self):
		return (self.name + ">>\n   " + ", ".join(self.domains) + "\n   " + ", ".join(self.resources))

	@property
	def types(self):
		return self.domains | self.resources

	def add_domain(self, domain):
		self.domains.add(domain)

	def add_resource(self, resource):
		self.resources.add(resource)

	#merge given domain group with self
	def merge(group):
		self.name = self.name if len(self.name) < len(group.name) else group.name
		self.domains |= group.domains
		self.resources |= group.resources

	def contains(self, type_):
		return (type_ in self.domains or type_ in self.resources) 

#is "x" in sorted list "slist" (can be substring of some item in slist) ?
def in_sorted(x, slist):
	first = (x.split("_"))[0]
	i = bisect.bisect_left(slist, first)
	if i == 0 and not slist[0].startswith(first):
		return False # not found
	#browse through items starting with the same word
	while(i < len(slist) and slist[i].startswith(first)):
		#exclude extension "exec" (domain entry point)
		if slist[i][-4:] == "exec":
			i += 1
			continue
		if slist[i].startswith(x):
			#print "found: " + slist[i]
			return True
		i += 1
	return False

# Find all items starting with "x" in sorted list "slist"
def find_in_sorted(x, slist):
	found = []
	i = bisect.bisect_left(slist, x)
	while i < len(slist) and slist[i].startswith(x):
		found.append(slist[i] + "_t")
		i += 1
	return found

# Find all items starting with "x" in sorted list "slist" and remove them from "slist"
def find_remove_sorted(x, slist):
	found = []
	i = bisect.bisect_left(slist, x)
	while i < len(slist) and slist[i].startswith(x):
		found.append(slist.pop(i) + "_t")
	return found

# Returns (domain) name corresponding to given label (finds longest part
# of given label that is also used somewhere in "object_list")
'''def subject_name(subject, object_list):
	s = subject.split("_")
	#print s
	for i in range(len(s)):
		#print s[:len(s)-i]
		#print "test" +  ("_".join(s[:-i]))
		if in_sorted("_".join(s[:len(s)-i]), object_list):
			return "_".join(s[:len(s)-i])
	return s[0]'''

def subject_name(subject, object_list):
	s = subject.split("_")
	return s[0]
# Returns dictionary "group_name":"DomainGroup()"
def create_domain_groups(subject_list, object_list):
	#subject_list.sort(reverse = True)
	domain_groups = {}
	for subject in subject_list:
		group_name = subject_name(subject, object_list)
		if group_name not in domain_groups:
			domain_groups[group_name] = DomainGroup(group_name)
		domain_groups[group_name].add_domain(subject+"_t")
	return domain_groups

# Fills "resources" attribute of "domain_groups" with 
# non-domain types corresponding to given group name 
def create_resource_groups(domain_groups, object_list):
	# copy object_list so that I can delete items using "find_remove_sorted"
	object_list_ = copy.deepcopy(object_list)
	#resource_groups = {}

	# Sort domain group names so that the longest ones are first
	# Eg. Resources of "systemd" should not contain resources of "systemd_networkd"
	domain_group_names = [x for x in domain_groups.keys()]
	domain_group_names.sort(reverse = True)
	for group_name in domain_group_names:
		domain_groups[group_name].resources = set(find_remove_sorted(group_name, object_list_))
		#print(domain_groups[group_name].resources)
	#print("\n".join(object_list_))
	return domain_groups


#returns list of types not assigned to any domain group
def get_unassigned_types():
	data.policy_init()
	
	domain_groups = group_types_name()

	type_list = set([str(x)[:-2].lower() for x in data.get_types()])

	#get types corresponding to "domains" - runnables
	subject_list = set([str(x)[:-2].lower() for x in data.get_domain_types()])

	object_list = sorted(type_list - subject_list)#, key=lambda s: s.lower())

	unassigned = list()
	for obj in object_list:
		for name,group in domain_groups.items():
			if obj+"_t" in group.resources:
				break
		else:
			unassigned.append(obj+"_t")
	return unassigned

# Returns dictionary "group_name":"set_of_corresponding_types"
# Combination of resource and domain grouping
#def create_type_groups

# Scan system for domain and object types and group them by name separating subject and objects
def group_types_name():
	data.policy_init()
	
	# get all type names and remove trailing "_t"
	type_list = set([str(x)[:-2].lower() for x in data.get_types()])

	#get types corresponding to "domains" - runnables
	subject_list = set([str(x)[:-2].lower() for x in data.get_domain_types()])

	object_list = sorted(type_list - subject_list)#, key=lambda s: s.lower())
	type_list = sorted(type_list)#, key=lambda s: s.lower())

	domain_groups = create_domain_groups(subject_list, object_list)
	
	domain_groups = create_resource_groups(domain_groups, object_list)

	return domain_groups

############################### cil module file based grouping #####################
# Scan system for domain and object types and group them
# according to cil module files located in "path"
# Results are printed to stdout (to be saved in domain_groups_cil.conf)
def parse_cil_files(path):
	data.policy_init()
	# get all types
	type_list = set([str(x).lower() for x in data.get_types()])
	#get types corresponding to "domains" - runnables
	subject_list = set([str(x).lower() for x in data.get_domain_types()])

	object_list = type_list - subject_list

	cil = pparse.get_types_cil(path)
	
	for (name,types) in cil:
		types = set(types)
		domains = types & subject_list
		resources = types - domains
		print(name,":",",".join(sorted(domains)),":", ",".join(sorted(resources)),sep="")

# load domain groups from domain_groups_cil.conf file
# and return them as ditionary {group_name:DomainGroup()}
def group_types_cil(): 
	try:
		txt = open("/etc/sepolicyanalysis/domain_groups_cil.conf", "r")

		domain_groups = {}
		for line in txt:
			# group_name:domain_types:resource_types
			line = line.strip()
			line = line.split(":")
			if len(line) == 3:
				new_group = DomainGroup(line[0])
				new_group.domains = set(line[1].split(","))
				new_group.resources = set(line[2].split(","))
				domain_groups[line[0]] = new_group

		return domain_groups

	except IOError as e:
		print(e,file=sys.stderr)
		return {}

#get types from given groups 
# returns (domains, resources)
def get_types(groups):
	domains = set()
	resources = set()

	for group in groups:
		domains |= group.domains
		resources |= group.resources

	return (domains, resources)

	#return domain_groups #, create_resource_groups(domain_groups, object_list)

#print subject_name(sys.argv[1], object_list)
#for subject in subject_list:
#	print subject + "-> " + subject_name(subject, object_list)
def print_domain_groups():

	domain_groups, resource_groups = group_types_name()

	domain_group_names = [x for x in domain_groups.keys()]
	domain_group_names.sort()
	for group in domain_group_names:
		#if "systemd" in group:
			print(group + ">>\n   " + ", ".join(domain_groups[group]) + "\n   " + ", ".join(resource_groups[group]) + "\n")



#print_domain_groups()
