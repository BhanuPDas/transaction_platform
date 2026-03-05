
In the followings dirs you will find the repective macromodules:
- 25-Node-Topology -> for the topology set up
- serf-comet-fullnode-tx -> for the set up of the transaction module

Set up first the topology and then the transaction module once the set up is completed in order to test the execution of transactions, go to the root folder on the specific containers (buyer) and run the python file ***main.py***.
In each respective dir you will find further informations on the setup.


This version of the 25 node implemantation includes a service discovery clustering, this consists into a restricted search of resources first limited to the belonging cluster, if resoruces are not found there then the seearch will be performed globally.
This lead to a different ip mapping from the uncluster version, some buyer and seller will be in the 1st cluster and come buyer and seller will belong to the second one as shown below.

### Switch A (1st cluster), BUYER nodes: serf1....serf6 buyer, VALIDATORS: serf11,12
```text
serf1  = 10.1.0.11      serf2  = 10.1.0.12      serf3  = 10.1.0.13
serf4  = 10.1.0.14      serf5  = 10.1.0.15      serf6  = 10.1.0.16
serf7  = 10.1.0.17      serf8  = 10.1.0.18      serf9  = 10.1.0.19
serf10 = 10.1.0.20      serf11 = 10.1.0.21      serf12 = 10.1.0.22 
```

### Switch B (2nd cluster), BUYER nodes: serf13....serf17 buyer, VALIDATORS: serf24,25
```text
serf13 = 10.2.0.11      serf14 = 10.2.0.12      serf15 = 10.2.0.13
serf16 = 10.2.0.14      serf17 = 10.2.0.15      serf18 = 10.2.0.16
serf19 = 10.2.0.17      serf20 = 10.2.0.18      serf21 = 10.2.0.19
serf22 = 10.2.0.20      serf23 = 10.2.0.21      serf24 = 10.2.0.22 
serf25 = 10.2.0.23
```
