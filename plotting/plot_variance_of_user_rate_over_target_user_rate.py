#!/usr/bin/env python

''' Plot standard deviation of delivered rate over target rate 
x axis: standard deviation delivered rate per user 
y axis: percentage of satisfied users 

'''

__author__ = "Hauke Holtkamp"
__credits__ = "Hauke Holtkamp"
__license__ = "unknown"
__version__ = "unknown"
__maintainer__ = "Hauke Holtkamp"
__email__ = "h.holtkamp@gmail.com" 
__status__ = "Development" 

def plot(filename):
    """ Open data file, process, generate pdf and png"""

    import numpy as np
    import matplotlib.pyplot as plt
    from utils import utils

    # data comes in a csv
    data = np.genfromtxt(filename, delimiter=',')/1e6 # Mbps 

    # first row is x-axis (number of users in cell). Each user has a fixed rate.
    x = data[0] # Mbps

    fig = plt.figure()
    ax1 = fig.add_subplot(111)
    # second row is BA
    ax1.plot(x, data[1], '-k+', label='Sequential alignment', markersize=10)
    
#    ax1.plot(x, data[2], '-ro', label='Random shift each iter', markersize=10)
    
#    ax1.plot(x, data[3], '-c^', label='Random shift once', markersize=10)

    ax1.plot(x, data[2], '-b*', label='Random alignment', markersize=10)

#    ax1.plot(x, data[4], '-cp', label='PF bandwidth adapting', markersize=10)


#    ax1.plot(x, data[5], '-yx', label='Random once', markersize=10)

    ax1.plot(x, data[3], '-gD', label='P-persistent ranking', markersize=10)
    
#    ax1.plot(x, data[7], '-kp', label='Static Reuse 3', markersize=10)
    
    ax1.plot(x, data[4], '-ms', label='DTX alignment with memory', markersize=10)

    plt.axis( [1, 3, 0, 3])
    plt.legend(loc='upper right', prop={'size':20})
    plt.setp(ax1.get_xticklabels(), fontsize=20)
    plt.setp(ax1.get_yticklabels(), fontsize=20)
    xlabel = 'User target rate in Mbps'
    ylabel = 'Standard deviation of \n achieved rate in Mbps'
    title  = 'Consumption over sum rate'
    ax1.set_xlabel(xlabel,size=20)
    ax1.set_ylabel(ylabel,size=20)
#    plt.title(title)
    plt.subplots_adjust(left=0.2)
    plt.savefig(filename+'.pdf', format='pdf')
    plt.savefig(filename+'.png', format='png')


if __name__ == '__main__':
    import sys
    filename = sys.argv[1]
    plot(filename)
