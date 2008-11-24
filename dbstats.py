#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-

try:
	from sqlite3 import connect as sqlite3_connect
except:
	from sqlite import connect as sqlite3_connect

import os

def dbutil_create_text_table_query(table, columns):
	query = "create table %s (%s)" % (table,
					  reduce(lambda a, b: a + ", %s" % b,
					   	 map(lambda a: "%s %s" % a,
						     columns)))
	return query

def dbutils_get_columns(cursor, table):
	cursor.execute('select * from %s where rowid = 1' % table)
	columns = [column[0] for column in cursor.description]
	columns.sort()
	return columns

def dbutils_add_missing_text_columns(cursor, table, old_columns, columns):
	for column in columns:
		if column[0] not in old_columns:
			cursor.execute("alter table %s add column %s %s" % (table,
									    column[0],
									    column[1]))

def get_sysinfo_dict(system):
	result = {}
	f = file(system + ".sysinfo")
	for line in f.readlines():
		line = line.strip()
		if len(line) == 0 or line[0] == "#":
			continue
		# Make sure we cope with the separator being in the field value
		# Ex.: "foo: bar:baz"
		# Should produce result["foo"] = "bar:baz"
		sep = line.index(":")
		result[line[:sep]] = line[sep + 1:].strip()
	f.close()
	return result

class dbstats:
	def __init__(self, appname):
		self.conn = sqlite3_connect("%s.db" % appname)
		self.cursor = self.conn.cursor()

		self.create_tables()

	system_tunings_columns = [ ( "tso", "text" ),
				   ( "ufo", "text" ),
				   ( "softirq_net_tx_prio", "text" ),
				   ( "softirq_net_rx_prio", "text" ),
				   ( "app_rtprio", "text" ),
				   ( "irqbalance", "text" ),
				   ( "app_affinity", "text" ),
				   ( "app_sched", "text" ),
				   ( "kcmd_isolcpus", "text" ),
				   ( "nic_kthread_affinities", "text" ),
				   ( "nic_kthread_rtprios", "text" ),
				   ( "oprofile", "text" ),
				   ( "systemtap", "text" ),
				   ( "kcmd_maxcpus", "text" ),
				   ( "vsyscall64", "text" ),
				   ( "futex_performance_hack", "text" ),
				   ( "kcmd_idle", "text" ),
				   ( "lock_stat", "text" ),
				   ( "tcp_congestion_control", "text" ),
				   ( "tcp_sack", "text" ),
				   ( "tcp_dsack", "text" ),
				   ( "tcp_window_scaling", "text" ),
				   ( "kcmd_nohz", "text" ),
				   ( "coalesce_rx_frames", "text" ),
				   ( "coalesce_tx_frames", "text" ),
				   ( "glibc_priv_futex", "text" ) ]

	def create_tables(self):
		query = dbutil_create_text_table_query("system_tunings", self.system_tunings_columns)
		try:
			self.cursor.execute(query)
		except:
			old_tunings_columns = dbutils_get_columns(self.cursor, "system_tunings")
			if [ a[0] for a in self.system_tunings_columns ] != old_tunings_columns:
				dbutils_add_missing_text_columns(self.cursor,
								 "system_tunings",
								 old_tunings_columns,
								 self.system_tunings_columns)

		try:
			self.cursor.execute('''
				create table machine_hardware (arch text, vendor text,
							       cpu_model text, nr_cpus int)
			''')
		except:
			pass

		try:
			self.cursor.execute('''
				create table machine (nodename text, hw int)
			''')
		except:
			pass

		software_versions_columns = [ ( "kernel_release", "text" ),
					      ( "libc", "text" ) ]
		query = dbutil_create_text_table_query("software_versions",
						       software_versions_columns)
		try:
			self.cursor.execute(query)
		except:
			old_software_versions_columns = dbutils_get_columns(self.cursor, "software_versions")
			if [ a[0] for a in software_versions_columns ] != old_software_versions_columns:
				dbutils_add_missing_text_columns(self.cursor,
								 "software_versions",
								 old_software_versions_columns,
								 software_versions_columns)

		try:
			self.cursor.execute('''
				create table environment (machine int,
							  system_tunings int,
							  software_versions int)
			''')
		except:
			pass

		# FIXME rename 'env' to 'server_env'
		try:
			self.cursor.execute('''
				create table report (env int,
						     client_env int,
						     ctime int,
						     filename text,
						     comment int)
			''')
		except:
			pass

		for metric in [ "avg", "min", "max", "dev" ]:
			try:
				self.cursor.execute('''
					create table latency_per_rate_%s (report int,
									  rate int,
									  value real)
				''' % metric)
			except:
				pass

		try:
			self.cursor.execute('''
				create table comment (comment text)
			''')
		except:
			pass

		self.conn.commit()

	def get_dict_table_id(self, table, parms):
		where_condition = reduce(lambda a, b: a + " and %s" % b,
					 map(lambda a: ('%s = "%s"' % (a, parms[a])),
					     parms.keys()))
		self.cursor.execute("select rowid from %s where %s" % (table,
								       where_condition))
		result = self.cursor.fetchone()
		if result:
			return result[0]
		return None

	def create_dict_table_id(self, table, parms):
		field_list = reduce(lambda a, b: a + ", %s" % b, parms.keys())
		values_list = reduce(lambda a, b: a + ", %s" % b,
				     map(lambda a: ('"%s"' % (parms[a])),
				     	 parms.keys()))
		query = '''
			insert into %s ( %s )
				      values ( %s )
			       ''' % (table, field_list, values_list)
		self.cursor.execute(query)
		self.conn.commit()

	def get_machine_hardware_id(self, parms):
		self.cursor.execute('''
			select rowid from machine_hardware where
				arch = "%s" and
				vendor = "%s" and
				cpu_model = "%s" and
				nr_cpus = %d
			       ''' % parms)
		result = self.cursor.fetchone()
		if result:
			return result[0]
		return None

	def create_machine_hardware_id(self, parms):
		self.cursor.execute('''
			insert into machine_hardware ( arch, vendor,
						       cpu_model, nr_cpus )
					      values ( "%s", "%s", "%s", %d )
			       ''' % parms)
		self.conn.commit()

	def get_machine_id(self, parms):
		self.cursor.execute('''
			select rowid from machine
				     where nodename = "%s" and hw = %d
			       ''' % parms)
		result = self.cursor.fetchone()
		if result:
			return result[0]
		return None

	def create_machine_id(self, parms):
		self.cursor.execute('''
			insert into machine ( nodename, hw )
				     values ("%s", %d )
			       ''' % parms)
		self.conn.commit()

	def get_env_id(self, parms):
		self.cursor.execute('''
			select rowid from environment
				     where machine = %d and
					   system_tunings = %d and
					   software_versions = %d
			       ''' % parms)
		result = self.cursor.fetchone()
		if result:
			return result[0]
		return None

	def create_env_id(self, parms):
		self.cursor.execute('''
			insert into environment ( machine, system_tunings,
						  software_versions )
					 values ( %d, %d, %d )
			       ''' % parms)
		self.conn.commit()

	def get_report_id(self, server_env, client_env, ctime, filename):
		self.cursor.execute('''
			select rowid from report where
				env = %d and
				client_env = %d and
				ctime = "%s" and
				filename = "%s"
			       ''' % (server_env, client_env, ctime, filename))
		result = self.cursor.fetchone()
		if result:
			return result[0]
		return None

	def create_report_id(self, server_env, client_env, ctime, filename):
		self.cursor.execute('''
			insert into report ( env, client_env, ctime, filename )
				    values ( %d, %d, "%s", "%s")
			       ''' % (server_env, client_env, ctime, filename))
		self.conn.commit()


	def get_max_rate_for_report(self, report):
		self.cursor.execute('''
					select max(rate)
					  from latency_per_rate_avg
					  where report = %d
				  ''' % report)
		results = self.cursor.fetchall()
		if results and results[0][0]:
			return int(results[0][0])
		return None

	def get_server_env_id_for_report(self, report):
		self.cursor.execute('select env from report where rowid = %d' % report)
		results = self.cursor.fetchone()
		if results:
			return int(results[0])
		return None

	def get_ctime_for_report(self, report):
		self.cursor.execute('select ctime from report where rowid = %d' % report)
		results = self.cursor.fetchone()
		if results:
			return int(results[0])
		return None

	def get_kernel_release_for_report(self, report):
		self.cursor.execute('''
					select s.kernel_release
					  from report rep,
					       environment env,
					       software_versions s
					  where rep.rowid = %d and
					  	rep.env = env.rowid and
					  	env.software_versions = s.rowid
				  ''' % report)
		results = self.cursor.fetchone()
		if results:
			return results[0]
		return None

	def get_libc_release_for_report(self, report):
		self.cursor.execute('''
					select s.libc
					  from report rep,
					       environment env,
					       software_versions s
					  where rep.rowid = %d and
					  	rep.env = env.rowid and
					  	env.software_versions = s.rowid
				  ''' % report)
		results = self.cursor.fetchone()
		if results:
			return results[0]
		return None

	def get_system_tunings_for_report(self, report):
		self.cursor.execute('''
					select r.env,
					       e.system_tunings,
					       s.kernel_release,
					       s.libc,
					       t.*
					  from report r,
					       environment e,
					       system_tunings t,
					       software_versions s
					  where r.env = e.rowid and
						e.system_tunings = t.rowid and
						e.software_versions = s.rowid and
						r.rowid = %d
				  ''' % report)
		return self.cursor.fetchone()

	def get_system_tunings_by_id(self, id):
		self.cursor.execute('''
					select *
					  from system_tunings
					  where rowid = %d
				  ''' % id)
		return self.cursor.fetchone()

	def get_system_tunings_ids_for_query(self, query):
		try:
			self.cursor.execute('''
						select rowid
						  from system_tunings
						  where %s
					  ''' % query)
			return [ id[0] for id in self.cursor.fetchall() ]
		except: 
			raise SyntaxError

	def machine_hardware_id(self, system):
		machine_hardware = (system["arch"],
				    system["vendor_id"],
				    system["cpu_model"],
				    int(system["nr_cpus"]))
		machine_hardware_id = self.get_machine_hardware_id(machine_hardware)
		if not machine_hardware_id:
			self.create_machine_hardware_id(machine_hardware)
			machine_hardware_id = self.get_machine_hardware_id(machine_hardware)

		return machine_hardware_id

	def machine_id(self, system, machine_hardware_id):
		machine = (system["nodename"], machine_hardware_id)
		machine_id = self.get_machine_id(machine)
		if not machine_id:
			self.create_machine_id(machine)
			machine_id = self.get_machine_id(machine)

		return machine_id

	def get_system_tunings_id(self, machine):
		system_tunings = {}

		# First get the tunings collected by ait-get-sysinfo.py
		for tuning in [ a[0] for a in self.system_tunings_columns ]:
			if machine.has_key(tuning):
				system_tunings[tuning] = machine[tuning]

		id = self.get_dict_table_id("system_tunings", system_tunings)
		if not id:
			self.create_dict_table_id("system_tunings", system_tunings)
			id = self.get_dict_table_id("system_tunings", system_tunings)

		return id

	def setreport(self, report, client_machine, server_machine):
		# Load the client and server hardware info from the data
		# collected by ait-get-sysinfo.py
		client_system = get_sysinfo_dict(client_machine)
		server_system = get_sysinfo_dict(server_machine)

		# Get the hardware ID for the client and server machines
		client_machine_hardware_id = self.machine_hardware_id(client_system)
		server_machine_hardware_id = self.machine_hardware_id(server_system)
		
		# Get the machine ID for the client and server machines
		client_machine_id = self.machine_id(client_system, client_machine_hardware_id)
		server_machine_id = self.machine_id(server_system, server_machine_hardware_id)

		# Find the server system tunings id in the DB
		system_tunings_id = self.get_system_tunings_id(server_system)

		# Collect the versions of relevant system components (kernel,
		# libc, etc):
		software_versions = {}
		software_versions["kernel_release"] = server_system["kernel_release"]
		if server_system.has_key("libc"):
			software_versions["libc"] = server_system["libc"]

		software_versions_id = self.get_dict_table_id("software_versions", software_versions)
		if not software_versions_id:
			self.create_dict_table_id("software_versions", software_versions)
			software_versions_id = self.get_dict_table_id("software_versions",
								      software_versions)
		
		# server_machine_id, system_tunings_id, kernel_release
		server_env_parms = (server_machine_id, system_tunings_id, software_versions_id)
		server_env_id = self.get_env_id(server_env_parms)

		ctime = os.stat(report).st_ctime

		if server_env_id:
			self.report = self.get_report_id(server_env_id, client_machine_id, ctime, report)
			if self.report:
				return False
		else:
			self.create_env_id(server_env_parms)
			server_env_id = self.get_env_id(server_env_parms)

		self.create_report_id(server_env_id, client_machine_id, ctime, report)
		self.report = self.get_report_id(server_env_id, client_machine_id, ctime, report)
		return True

	def insert_latency_per_rate(self, metric, rates):
		for rate in rates.keys():
			self.cursor.execute('''
				insert into latency_per_rate_%s ( report, rate, value )
					     values ( %d, %d, "%f" )
				       ''' % (metric, self.report,
				       	      rate, rates[rate]))
		self.conn.commit()
