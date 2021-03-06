#!/usr/bin/env python

''' Resource Allocation using Power control and Sleep as described in my academic papers, mostly in the JSAC one.

This is performed within a base station or sector. For all associated mobiles, allocate powers and sleep modes over the OFDMA frame.

File: RAPS.py
'''

__author__ = "Hauke Holtkamp"
__credits__ = "Hauke Holtkamp"
__license__ = "unknown"
__version__ = "unknown"
__maintainer__ = "Hauke Holtkamp"
__email__ = "h.holtkamp@gmail.com" 
__status__ = "Development" 

from world import mobile 
import numpy as np
from quantmap import quantmap
from rcg import rcg
from iwf import iwf
from utils import utils
from optim import optimMinPow
from scipy import linalg
import logging
logger = logging.getLogger('RAPS_script')

def raps(wrld, cell, mobiles, rate, plotting=False):
    """In the cell, allocate powers and sleep modes to mobiles."""
    # need to map algorithm indices to mobile ids (artifact from MATLAB)
    id_map = dict()
    for k, mob in enumerate(mobiles):
        id_map[k] = mob.id_
    
    # Make sure all mobiles are associated with the cell correctly
    for mob in mobiles:
        if mob.cell != cell:
            raise ValueError('Faulty passing of mobiles to RAPS')
    logger.info( '{0:50} {1:5d}'.format('Mobiles in this cell:', len(mobiles)))

    # Build SINR arrays
    users = len(mobiles) 
    N = wrld.PHY.numFreqChunks
    T = wrld.PHY.numTimeslots
    noisePower = wrld.wconf.systemNoisePower

    # EC_Optim contains one MIMO value per mobile (the center chunk effective channel)
    EC_Optim = np.empty([users, cell.antennas, wrld.mobiles[0].antennas], dtype=complex) # TODO Will we ever have mobiles with different numbers of annteas?
    # SINR_Quant contains one value for each RB and user
    SINR_Quant = np.empty([N, T, users]) 
    centerChunkIndex = np.floor(N/2)
    whichTimeslotIndex = list(cell.sleep_slot_priority).index(0)
    for idx, mob in enumerate(mobiles):
        EC_Optim[idx,:,:] = mob.OFDMA_EC[:,:,centerChunkIndex,whichTimeslotIndex] / N # scale this effective channel over all chunks
        SINR_Quant[:,:,idx] = np.mean(mob.OFDMA_effSINR,0) # SINR for RCG 

    ### Step 1 ###
    # Optimization call
    pSupplyOptim, resourceAlloc, status = optimMinPow.optimizePCDTX(EC_Optim, np.ones(EC_Optim.shape[0]), rate, wrld.PHY.systemBandwidth, cell.pMax, mobiles[0].BS.p0, mobiles[0].BS.m, mobiles[0].BS.pS)
    logger.debug( 'Resource Allocation: ' + str(resourceAlloc))
    logger.debug( 'Sleep priority: ' + str(cell.sleep_slot_priority))
    logger.info( '{0:50} {1:5.2f} W'.format('Real-valued optimization objective:', pSupplyOptim) )
    
    ## Plot ##
    if cell.cellid == 12345 and plotting: # center in tier 1
        from plotting import channelplotter
        channelplotter.bar(np.mean(np.mean(EC_Optim,1),1),'Abs mean of MIMO EC Optim', 'sinr_optim.pdf')
        channelplotter.OFDMAchannel(SINR_Quant, 'SINR Quant', 'sinr_quant.pdf')
        channelplotter.bar(resourceAlloc,'Resource Share Optim', 'rscshare.pdf')
        import pdb; pdb.set_trace()
    
    ### Step 2 ###

    # Map real valued solution to OFDMA frame
    # QUANTMAP
    resourcesPerTimeslot = quantmap.quantmap(resourceAlloc, N, T)
    outmap = np.empty([N, T])

    # Handle sleep slot alignment here. 
    resourcesPerTimeslot = resourcesPerTimeslot[cell.sleep_slot_priority]

    # RCG
    for t in np.arange(T):
        outmap[:,t],_ = rcg.rcg(SINR_Quant[:,t,:],resourcesPerTimeslot[t,:]) # outmap.shape = (N,T) tells the user index

    # Given allocation and rate target, we inverse waterfill channels for each user separately on the basis of full SINR 
    # IWF
    powerlvls = np.empty([N, T, mob.antennas])
    powerlvls[:] = np.nan
    
    for idx, obj in enumerate(mobiles): 
        # grab user SINR
        EC_usr = obj.OFDMA_EC[:,:,outmap==idx] # all effective channels assigned to this user
        noiseIfPower_usr = np.real(EC_usr[0,0,:].repeat(2) * 0 + 1) # TODO remove later  #(obj.baseStations[obj.BS].cells[obj.cell].OFDMA_interferencePower + obj.baseStations[obj.BS].cells[obj.cell].OFDMA_noisePower) * np.ones(SINR_user_all[0,0,:,:].shape)[outmap==idx].ravel().repeat(2) # one IF value per resource, so repeat once to match spatial channels
        # create list of eigVals
        eigVals = np.real([linalg.eig(EC_usr[:,:,i])[0] for i in np.arange(EC_usr.shape[2])]).ravel() # two eigvals (spatial channels) per resource
        targetLoad = rate * wrld.PHY.simulationTime 
        # inverse waterfill and fill back to OFDMA position
        powlvl, waterlvl, cap = iwf.inversewaterfill(eigVals, targetLoad, noiseIfPower_usr, wrld.PHY.systemBandwidth / N, wrld.PHY.simulationTime / T)
        powerlvls[outmap==idx,:] = powlvl.reshape(EC_usr.shape[2],obj.antennas)

    ptx = np.array([np.nansum(np.nansum(powerlvls[:,t,:],axis=0),axis=0) for t in np.arange(T)])
    logging.debug('Ptx' + str(ptx))
    if (ptx > cell.pMax).any(): 
        raise ValueError('Transmission power too high in IWF: '+str(ptx)+ ' W')
        
    # Store power levels in cell for next round
    cell.OFDMA_power[:] = np.swapaxes(np.swapaxes(powerlvls[:],1,2),0,1) 
    cell.OFDMA_power[np.isnan(cell.OFDMA_power)] = 0
    # remap to mobile ids
    outmap_ids = np.copy(outmap)
    for k,v in id_map.iteritems():
        outmap_ids[outmap==k] = v
    cell.outmap = outmap_ids
        
    psupplyPerSlot = mobiles[0].BS.p0 + mobiles[0].BS.m * ptx
        
    psupplyPerSlot[np.isnan(psupplyPerSlot)] = mobiles[0].BS.pS
    pSupplyQuant = np.mean(psupplyPerSlot)
    logger.info( '{0:50} {1:5.2f} W'.format('Integer-valued optimization objective:', pSupplyQuant))

    return pSupplyOptim, pSupplyQuant


def capacity_achieved_per_mobile(target, wrld, cell, mobiles):
    '''Returns list in length of number of mobiles in cell indicating capacity achieved (True) or not (False) for each mobile.'''
    li = []
    for idx, mob in enumerate(mobiles):
        cap = achieved_capacity_on_mobile(wrld, cell, mobiles, idx)
        if cap < target:
            li.append(False)
        else:
            li.append(True)

    return li

def achieved_capacity_in_cell(wrld, cell, mobiles):
    """Returns cell capacity (all users) for this frame."""
    cap = 0
    for idx, mob in enumerate(mobiles):
        cap += achieved_capacity_on_mobile(wrld, cell, mobiles, idx)

    return cap

def achieved_capacity_on_mobile(wrld, cell, mobiles, user):
    """Calculate achieved link bit load of one user for this frame."""
    import pdb; pdb.set_trace()
    
    mobile_id = mobiles[user].id_
    n, t = np.where(cell.outmap==mobile_id)
    
    N = wrld.PHY.numFreqChunks
    T = wrld.PHY.numTimeslots
    systemBandwidth = wrld.PHY.systemBandwidth
    totalTime = wrld.PHY.simulationTime
    resourceTime = totalTime / T
    resourceBandwidth = systemBandwidth / N

    cap = 0
    for i in np.arange(len(n)):
        power = cell.OFDMA_power[:]
        cap += RB_bit_capacity(mobiles[user], n[i], t[i], resourceBandwidth, 
                resourceTime, power)

    return cap
