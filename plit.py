#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-

try:
	from sqlite3 import connect as sqlite3_connect
except:
	from sqlite import connect as sqlite3_connect

from dbstats import dbstats
import utilist, rit

metric_captions = {
	"avg": "Average Latency",
	"min": "Minimum Latency",
	"max": "Maximum Latency",
	"dev": "Latency Deviation"
}

def get_results(db, metric, report):
	db.cursor.execute('''
				select value, rate
				  from latency_per_rate_%s
				  where report = %d
				  order by rate
			  ''' % (metric, report))
	return db.cursor.fetchall()

def pylab_formatter_ms(x, pos = 0):
	ms = x / 1000
	us = x % 1000
	s = "%d" % ms
	if us > 0:
		s += ".%03d" % us
		s = s.rstrip('0')
	s += "ms"

	return s

def remove_nan(value):
	if value == 'nan':
		return 0.0
	return value

inches = 0.00666667

def plot_metric_report(ax, info, ymin, ymax, seq):
	xtickfontsize = 8
	ytickfontsize = 8

	ax.grid(False)

	ax.plot(info["rates"][:-1], info["values"][:-1], info["color"])

	ax.set_ylim(ymin, ymax)
	ylabel = "%s, rep=%d, max_rate=%d" % (info["kernel_release"],
					      info["report"],
					      info["max_report_rate"])
	ax.annotate(ylabel, xy = (85, 360 - 11 * seq),
		    xycoords='figure points',
		    fontname='Bitstream Vera Sans',
		    fontsize=8, color=info["color"])
	
	for label in ax.get_xticklabels():
		label.set(fontsize = xtickfontsize)
	for label in ax.get_yticklabels():
		label.set(fontsize = ytickfontsize)

def plot_metric(metric, ref, others):
	from matplotlib import use as muse
	muse('Agg')
	from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
	from matplotlib.figure import Figure
	from matplotlib.ticker import FuncFormatter

	green_font = { 'fontname'   : 'Bitstream Vera Sans',
		       'color'      : 'g',
		       'fontweight' : 'bold',
		       'fontsize'   : 10 }

	width  = 1250 * inches
	height = 880 * inches

	fig = Figure(figsize = (width, height))
	canvas = FigureCanvas(fig)

	# Reference results

	ax1 = fig.add_subplot(111)

	all = [ ]
	for other in others:
		all += other["values"][:-1]
	ylabels = list(set(ref["values"][:-1] + all))
	del all
	if 'nan' in ylabels:
		ylabels = [ remove_nan(p) for p in ylabels ]
	ylabels.sort()
	ymin = min(ylabels)
	ymax = max(ylabels)

	caption = metric
	if metric_captions.has_key(metric):
		caption = metric_captions[metric]
	ax1.set_title("%d %s samples" % (len(other["rates"]), caption), green_font)

	ax1.set_ylabel(caption, green_font)
	ax1.set_xlabel("Packet Rate", green_font)

	ax1.yaxis.set_major_formatter(FuncFormatter(pylab_formatter_ms))

	plot_metric_report(ax1, ref, ymin, ymax, 0)

	seq = 1;
	for other in others:
		ax2 = fig.add_axes(ax1.get_position(), sharex = ax1, sharey = ax1, frameon = False)
		plot_metric_report(ax2, other, ymin, ymax, seq)
		seq += 1
		del ax2

	list_others = utilist.csv([ o["report"] for o in others ], "%d")

	canvas.print_figure("%d_%s_%s.png" % (ref["report"], list_others, metric))
	del fig, canvas, ax1

xlabels = []

def pylab_formatter_report(x, pos = 0):
	if pos > 0 and pos <= len(xlabels):
		return xlabels[pos - 1]
	return ""

def plot_max_rates(ref, others):
	global xlabels

	from matplotlib import use as muse
	muse('Agg')
	from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
	from matplotlib.figure import Figure
	from matplotlib.ticker import FuncFormatter

	green_font = { 'fontname'   : 'Bitstream Vera Sans',
		       'color'      : 'g',
		       'fontweight' : 'bold',
		       'fontsize'   : 10 }

	width  = 1250 * inches
	height = 880 * inches

	fig = Figure(figsize = (width, height))
	canvas = FigureCanvas(fig)

	# Reference results

	ax1 = fig.add_subplot(111)

	all = [ ref["max_report_rate"] ]
	for other in others:
		all.append(other["max_report_rate"])
	ylabels = list(set(all))
	del all
	ylabels.sort()
	ymin = min(ylabels)
	ymax = max(ylabels)
	#print "ymin=%f, ymax=%f" % (ymin, ymax)
	ax1.set_ylim(0, ymax)
	ax1.set_autoscale_on(False)
	#ax1.set_yticks(range(ymin, ymax, 3000))
	#ax1.grid(True)

	xlabels = [ ref["report"] ] + [ a["report"] for a in others ]
	ax1.set_xlim(0, len(xlabels) + 1)
	ax1.xaxis.set_major_formatter(FuncFormatter(pylab_formatter_report))

	ax1.set_title("Maximum Rates Achieved", green_font)

	ax1.set_ylabel("Maximum Rate", green_font)
	ax1.set_xlabel("Report ID", green_font)

	i = 0
	for a in [ ref, ] + others:
		ax1.bar(0.75 + i, a["max_report_rate"], width=0.5, color=a["color"])
		i += 1

	list_others = utilist.csv([ o["report"] for o in others ], "%d")

	canvas.print_figure("%d_%s_max_rates.png" % (ref["report"], list_others))
	del fig, canvas, ax1

colors = ( "b", "r", "g", "c", "m", "y", "k" )
color_index = 0
html_colors = { "b" : "blue",
		"r" : "red",
		"g" : "green",
		"c" : "cyan",
		"m" : "magenta",
		"y" : "yellow",
		"k" : "brown"
	       }
	
def get_report_info(db, report, metric):
	global color_index
	results = get_results(db, metric, report)
	info = {}
	info["report"] = report
	info["kernel_release"] = db.get_kernel_release_for_report(report)
	info["libc"] = db.get_libc_release_for_report(report)
	info["max_report_rate"] = db.get_max_rate_for_report(report)
	info["values"] = [ i[0] for i in results ]
	info["rates"] = [ i[1] for i in results ]
	info["color"] = colors[color_index]
	color_index += 1
	del results
	return info

def get_common_columns(results, columns):
	common_columns = []
	for column_index in range(len(columns)):
		if len(list(set([result["tunings"][column_index] for result in results]))) == 1:
			common_columns.append(column_index)

	return common_columns

metrics = [ "avg", "dev", "min", "max" ]

def create_html(db, ref, others):
	list_others = utilist.csv([ o["report"] for o in others ], "%d")

	prefix="%d_%s" % (ref["report"], list_others)
	f = file("%d_%s.html" % (ref["report"], list_others), "w")

	f.write('''
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
        "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<title>Reports: %s</title>
</head>
<body>
<img src="%s_%s.png">
''' % ([ref["report"]] + [o["report"] for o in others], prefix, metrics[0]))

	ref["tunings"] = db.get_tunings_for_report(ref["report"])
	for other in others:
		other["tunings"] = db.get_tunings_for_report(other["report"])
	
	columns = [column[0] for column in db.cursor.description]
	common_columns = get_common_columns([ ref, ] + others, columns)

	f.write('<h1>Specific Tunings:</h0><table border=1 style="background-color: #8aa;400px; border: thin solid black; font-family: sans-serif; font-size: 10px;"><tr>')
	f.write("<th>report</th><th>max<br>packet<br>rate</th>")
	for column in range(len(columns)):
		if column not in common_columns:
			f.write("<th>%s</th>" % columns[column].replace("_", "<br>"))

	color_index = 0
	f.write('</tr><tr>')

	f.write('<td style="background-color: %s">%s</td>' % (html_colors[colors[color_index]], ref["report"]))
	f.write('<td>%d</td>' % ref["max_report_rate"])
	color_index += 1
	for field in range(len(columns)):
		if field not in common_columns:
			f.write("<td>%s</td>" % ref["tunings"][field])

	for other in others:
		f.write('</tr><tr>')

		f.write('<td style="background-color: %s">%s</td>' % (html_colors[colors[color_index]], other["report"]))
		f.write('<td>%d</td>' % other["max_report_rate"])
		color_index += 1
		for field in range(len(columns)):
			if field not in common_columns:
				f.write("<td>%s</td>" % other["tunings"][field])

	f.write('</tr><tr></table>')

	f.write('<h1>Common Tunings:</h1><table border=1 style="background-color: #8aa;400px; border: thin solid black; font-family: sans-serif; font-size: 10px;"><tr>')
	for column in common_columns:
		f.write("<th>%s</th>" % columns[column].replace("_", "<br>"))
	f.write('</tr><tr>')
	for column in common_columns:
		f.write("<td>%s</td>" % ref["tunings"][column])
		
	f.write("</tr></table>")
	for metric in metrics[1:]:
		f.write('<img src="%s_%s.png">' % (prefix, metric))
	f.write('<img src="%s_max_rates.png">' % prefix)
	f.write("</tr></table></body></html>")

	f.close()

def plot_metric_graphs(db, metric, ref_report, reports, plot_max):
	global color_index
	color_index = 0
	ref = get_report_info(db, ref_report, metric)
	others = []
	for other in reports.split(","):
		others.append(get_report_info(db, int(other), metric))

	plot_metric(metric, ref, others)
	if plot_max:
		plot_max_rates(ref, others)
		create_html(db, ref, others)

if __name__ == '__main__':
	import sys

	appname = sys.argv[1]
	ref_report = int(sys.argv[2])
	reports = sys.argv[3]

	db = dbstats(appname)
	plot_max = True
	for metric in metrics:
		plot_metric_graphs(db, metric, ref_report, reports, plot_max)
		plot_max = False
