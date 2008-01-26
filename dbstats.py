#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-

try:
	from sqlite3 import connect as sqlite3_connect
except:
	from sqlite import connect as sqlite3_connect

import ethtool
import schedutils
import os, sys
import procfs
import utilist

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

def get_tso_state():
	state=""
	for iface in ethtool.get_devices():
		try:
			state += "%s=%d," % (iface, ethtool.get_tso(iface))
		except:
			pass
	state = state.strip(",")
	return state

def get_ufo_state():
	state=""
	# UFO may not be present on this kernel and then we get an exception
	try:
		for iface in ethtool.get_devices():
			state += "%s=%d," % (iface, ethtool.get_ufo(iface))
	except:
		pass
	state = state.strip(",")

	return state

def get_nic_kthread_affinities(irqs):
	state=""
	for iface in ethtool.get_devices():
		irq = irqs.find_by_user(iface)
		if not irq:
			continue
		# affinity comes from /proc/irq/N/smp_affinities, that
		# needs root priviledges
		try:
			state += "%s=%s;" % (iface, utilist.csv(utilist.hexbitmask(irqs[irq]["affinity"], irqs.nr_cpus), '%x'))
		except:
			pass
	state = state.strip(";")
	return state

def get_nic_kthread_rtprios(irqs, ps):
	state=""
	for iface in ethtool.get_devices():
		irq = irqs.find_by_user(iface)
		if not irq:
			continue
		pids = ps.find_by_name("IRQ-%s" % irq)
		if not pids:
			continue
		state += "%s=%s;" % (iface, ps[pids[0]]["stat"]["rt_priority"])
	state = state.strip(";")
	return state

class dbstats:
	def __init__(self, appname):
		self.conn = sqlite3_connect("%s.db" % appname)
		self.cursor = self.conn.cursor()

		self.create_tables()

	def create_tables(self):
		system_tunings_columns = [ ( "tso", "text" ),
					    ( "ufo", "text" ),
					    ( "softirq_net_tx_prio", "text" ),
					    ( "softirq_net_rx_prio", "text" ),
					    ( "server_rtprio", "text" ),
					    ( "irqbalance", "text" ),
					    ( "server_affinity", "text" ),
					    ( "server_sched", "text" ),
					    ( "isolcpus", "text" ),
					    ( "nic_kthread_affinities", "text" ),
					    ( "nic_kthread_rtprios", "text" ),
					    ( "oprofile", "text" ),
					    ( "systemtap", "text" ),
					    ( "maxcpus", "text" ),
					    ( "vsyscall64", "text" ),
					    ( "futex_performance_hack", "text" ),
					    ( "idle", "text" ),
					    ( "lock_stat", "text" ) ]
		system_tunings_columns.sort()
		query = dbutil_create_text_table_query("system_tunings", system_tunings_columns)
		try:
			self.cursor.execute(query)
		except:
			old_tunings_columns = dbutils_get_columns(self.cursor, "system_tunings")
			if [ a[0] for a in system_tunings_columns ] != old_tunings_columns:
				dbutils_add_missing_text_columns(self.cursor,
								 "system_tunings",
								 old_tunings_columns,
								 system_tunings_columns)

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
		# For now client_env is an index into the 'client_machine' table,
		# but should be an index into the environment table, with
		# client environment being collected in ait.sh
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

		try:
			self.cursor.execute('''
				create table client_machine (nodename text)
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

	def get_client_machine_id(self, parms):
		self.cursor.execute('''
			select rowid from client_machine
				     where nodename = "%s"
			       ''' % parms)
		result = self.cursor.fetchone()
		if result:
			return result[0]
		return None

	def create_client_machine_id(self, parms):
		self.cursor.execute('''
			insert into client_machine ( nodename )
					    values ("%s" )
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

	def setreport(self, report, server_process_name, client_machine):
		pfs = procfs.stats()
		kcmd = procfs.cmdline()
		irqs = procfs.interrupts()
		cpuinfo = procfs.cpuinfo()
		uname = os.uname()

		# arch, vendor, cpu_model, nr_cpus
		machine_hardware_parms = (uname[4], cpuinfo["vendor_id"],
					  cpuinfo["model name"],
					  cpuinfo.nr_cpus)
		machine_hardware = self.get_machine_hardware_id(machine_hardware_parms)
		if not machine_hardware:
			self.create_machine_hardware_id(machine_hardware_parms)
			machine_hardware = self.get_machine_hardware_id(machine_hardware_parms)
		
		# nodename, hw
		machine_parms = (uname[1], machine_hardware)
		machine = self.get_machine_id(machine_parms)
		if not machine:
			self.create_machine_id(machine_parms)
			machine = self.get_machine_id(machine_parms)

		client_machine_id = self.get_client_machine_id(client_machine)
		if not client_machine_id:
			self.create_client_machine_id(client_machine)		
			client_machine_id = self.get_client_machine_id(client_machine)

		system_tunings = {}

		system_tunings["tso"] = get_tso_state()
		system_tunings["ufo"] = get_ufo_state()
		system_tunings["softirq_net_tx_prio"] = pfs.get_per_cpu_rtprios("softirq-net-tx")
		system_tunings["softirq_net_rx_prio"] = pfs.get_per_cpu_rtprios("softirq-net-rx")
		system_tunings["server_rtprio"] = pfs.get_rtprios(server_process_name)

		system_tunings["irqbalance"] = 0
		if pfs.find_by_name("irqbalance"):
			system_tunings["irqbalance"] = 1

		system_tunings["oprofile"] = 0
		if pfs.find_by_name("oprofiled"):
			system_tunings["oprofile"] = 1

		system_tunings["systemtap"] = 0
		if pfs.find_by_name("staprun"):
			system_tunings["systemtap"] = 1

		server = pfs.find_by_name(server_process_name)
		system_tunings["server_affinity"] = utilist.csv(utilist.hexbitmask(schedutils.get_affinity(server[0]), irqs.nr_cpus), "%x")
		system_tunings["server_sched"] = schedutils.schedstr(schedutils.get_scheduler(server[0]))

		if kcmd.options.has_key("isolcpus"):
			system_tunings["isolcpus"] = kcmd.options["isolcpus"]
		elif kcmd.options.has_key("default_affinity"):
			system_tunings["isolcpus"] = "da:%s" % kcmd.options["default_affinity"]
		else:
			system_tunings["isolcpus"] = None

		system_tunings["maxcpus"] = None
		if kcmd.options.has_key("maxcpus"):
			system_tunings["maxcpus"] = kcmd.options["maxcpus"]

		system_tunings["nic_kthread_affinities"] = get_nic_kthread_affinities(irqs)
		system_tunings["nic_kthread_rtprios"] = get_nic_kthread_rtprios(irqs, pfs)

		system_tunings["vsyscall64"] = None
		try:
			f = file("/proc/sys/kernel/vsyscall64")
			system_tunings["vsyscall64"] = int(f.readline())
			f.close()
		except:
			pass

		system_tunings["futex_performance_hack"] = None
		try:
			f = file("/proc/sys/kernel/futex_performance_hack")
			system_tunings["futex_performance_hack"] = int(f.readline())
			f.close()
		except:
			pass

		system_tunings["idle"] = None
		if kcmd.options.has_key("idle"):
			system_tunings["idle"] = kcmd.options["idle"]

		system_tunings["lock_stat"] = os.access("/proc/lock_stat", os.F_OK)

		system_tunings_id = self.get_dict_table_id("system_tunings", system_tunings)
		if not system_tunings_id:
			self.create_dict_table_id("system_tunings", system_tunings)
			system_tunings_id = self.get_dict_table_id("system_tunings", system_tunings)

		# Collect the versions of relevant system components (kernel,
		# libc, etc):
		software_versions = {}
		software_versions["kernel_release"] = uname[2] 

		# Default: libc statically linked
		software_versions["libc"] = None
		# Discover which libc is being used by the server process
		smaps_server = procfs.smaps(server[0])
		if smaps_server:
			libc = smaps_server.find_by_name_fragment("/libc-")
			if libc:
				software_versions["libc"] = libc[0].name

		software_versions_id = self.get_dict_table_id("software_versions", software_versions)
		if not software_versions_id:
			self.create_dict_table_id("software_versions", software_versions)
			software_versions_id = self.get_dict_table_id("software_versions",
								      software_versions)
		
		# machine, system_tunings_id, kernel_release
		server_env_parms = (machine, system_tunings_id, software_versions_id)
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
