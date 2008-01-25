#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-

import os

class sysctl:
	def __init__(self):
		self.cache = {}

	def __getitem__(self, key):
		if not self.cache.has_key(key):
			value = self.read(key)
			if value == None:
				return None
			self.cache[key] = value

		return self.cache[key]

	def __setitem__(self, key, value):
		oldvalue = self[key]

		if oldvalue == None:
			raise IOError
		elif oldvalue != value:
			self.write(key, value)
			self.cache[key] = value

	def keys(self):
		return self.cache.keys()

	def read(self, key):
		try:
			f = file("/proc/sys/%s" % key.replace(".", "/"))
		except:
			return None
		value = f.readline().strip()
		f.close()
		return value

	def write(self, key, value):
		try:
			f = file("/proc/sys/%s" % key.replace(".", "/"), "w")
		except:
			return
		f.write(value)
		f.close()

	def refresh(self):
		for key in self.cache():
			del self.cache[key]
			value = self.read(key)
			if value != None:
				self.cache[key] = value

if __name__ == '__main__':

	s = sysctl()

	print s["net.core.rmaem_max"]
	print s["net.core.wmem_max"]
	print s["net.core.rmem_max"]
	s["net.core.rmem_max"] = "%s" % (int(s["net.core.rmem_max"]) * 2)
	print s["net.core.rmem_max"]

	for i in s.keys():
		print "%s: %s" % (i, s[i])
