# System setup and execution

This repository contains the various of implemantations, in each directory you will all the modules starting from the topology up to the transation module and everything in between, they will be modified and updated once a version is stable.

- If you are starting fro scratch from a new server fisrt thing to do is install all the app you will need, for doing this go to: https://github.com/Edge-Emulator/Edge-Emulator and from there execute start.sh in your server.
- Once done this you can start setting up the preferred topology, for doing this simply follow the instruction in the respective topology directory. 
- For exemple here 50_nodes_unclustered/50-Node-Topology in the README file you will find all the steps to configure the 50 node unclustered topology.
- After the topolgy, set up the transaction module, for exemple for the 50 node topology unclustered go here 50_nodes_unclustered/serf-comet-fullnode-tx and follow the instruction on the README.


Remember to set up first the topology and then the transaction module once the setup is completed, in order to test the execution of transactions go to the root folder on the specific containers (Ex: serf3) and run the python file ***main.py***.

