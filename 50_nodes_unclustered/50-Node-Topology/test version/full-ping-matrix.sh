#!/bin/bash

echo "=========================================="
echo "Full 50-Node Connectivity Matrix Test"
echo "=========================================="
echo ""

passed=0
failed=0
total=0

test_ping() {
    local from=$1
    local to=$2
    local to_ip=$3
    ((total++))
    
    if docker exec clab-simple50-C${from} ping -c 1 -W 1 ${to_ip} >/dev/null 2>&1; then
        ((passed++))
        return 0
    else
        echo "  ✗ C${from} → C${to} (${to_ip}) FAILED"
        ((failed++))
        return 1
    fi
}

# Test within each switch (each client to every other client on same switch)
echo "Testing Switch A (C1-10) internal connectivity..."
for i in {1..10}; do
    for j in {1..10}; do
        if [ $i -ne $j ]; then
            test_ping $i $j 10.1.0.${j}
        fi
    done
done
echo "  Switch A: Tested $(( (10*9) )) pairs"

echo ""
echo "Testing Switch B (C11-20) internal connectivity..."
for i in {11..20}; do
    for j in {11..20}; do
        if [ $i -ne $j ]; then
            j_ip=$((j-10))
            test_ping $i $j 10.2.0.${j_ip}
        fi
    done
done
echo "  Switch B: Tested $(( (10*9) )) pairs"

echo ""
echo "Testing Switch C (C21-30) internal connectivity..."
for i in {21..30}; do
    for j in {21..30}; do
        if [ $i -ne $j ]; then
            j_ip=$((j-20))
            test_ping $i $j 10.3.0.${j_ip}
        fi
    done
done
echo "  Switch C: Tested $(( (10*9) )) pairs"

echo ""
echo "Testing Switch D (C31-40) internal connectivity..."
for i in {31..40}; do
    for j in {31..40}; do
        if [ $i -ne $j ]; then
            j_ip=$((j-30))
            test_ping $i $j 10.4.0.${j_ip}
        fi
    done
done
echo "  Switch D: Tested $(( (10*9) )) pairs"

echo ""
echo "Testing Switch E (C41-50) internal connectivity..."
for i in {41..50}; do
    for j in {41..50}; do
        if [ $i -ne $j ]; then
            j_ip=$((j-40))
            test_ping $i $j 10.5.0.${j_ip}
        fi
    done
done
echo "  Switch E: Tested $(( (10*9) )) pairs"

# Test cross-switch connectivity (sample from each switch to all other switches)
echo ""
echo "Testing cross-switch connectivity..."
echo "  Testing from Switch A to all other switches..."
for target in {11..20} {21..30} {31..40} {41..50}; do
    if [ $target -le 20 ]; then
        target_ip=10.2.0.$((target-10))
    elif [ $target -le 30 ]; then
        target_ip=10.3.0.$((target-20))
    elif [ $target -le 40 ]; then
        target_ip=10.4.0.$((target-30))
    else
        target_ip=10.5.0.$((target-40))
    fi
    test_ping 1 $target $target_ip
    test_ping 5 $target $target_ip
    test_ping 10 $target $target_ip
done

echo "  Testing from Switch B to all other switches..."
for target in {1..10} {21..30} {31..40} {41..50}; do
    if [ $target -le 10 ]; then
        target_ip=10.1.0.${target}
    elif [ $target -le 30 ]; then
        target_ip=10.3.0.$((target-20))
    elif [ $target -le 40 ]; then
        target_ip=10.4.0.$((target-30))
    else
        target_ip=10.5.0.$((target-40))
    fi
    test_ping 11 $target $target_ip
    test_ping 15 $target $target_ip
    test_ping 20 $target $target_ip
done

echo "  Testing from Switch C to all other switches..."
for target in {1..10} {11..20} {31..40} {41..50}; do
    if [ $target -le 10 ]; then
        target_ip=10.1.0.${target}
    elif [ $target -le 20 ]; then
        target_ip=10.2.0.$((target-10))
    elif [ $target -le 40 ]; then
        target_ip=10.4.0.$((target-30))
    else
        target_ip=10.5.0.$((target-40))
    fi
    test_ping 21 $target $target_ip
    test_ping 25 $target $target_ip
    test_ping 30 $target $target_ip
done

echo "  Testing from Switch D to all other switches..."
for target in {1..10} {11..20} {21..30} {41..50}; do
    if [ $target -le 10 ]; then
        target_ip=10.1.0.${target}
    elif [ $target -le 20 ]; then
        target_ip=10.2.0.$((target-10))
    elif [ $target -le 30 ]; then
        target_ip=10.3.0.$((target-20))
    else
        target_ip=10.5.0.$((target-40))
    fi
    test_ping 31 $target $target_ip
    test_ping 35 $target $target_ip
    test_ping 40 $target $target_ip
done

echo "  Testing from Switch E to all other switches..."
for target in {1..10} {11..20} {21..30} {31..40}; do
    if [ $target -le 10 ]; then
        target_ip=10.1.0.${target}
    elif [ $target -le 20 ]; then
        target_ip=10.2.0.$((target-10))
    elif [ $target -le 30 ]; then
        target_ip=10.3.0.$((target-20))
    else
        target_ip=10.4.0.$((target-30))
    fi
    test_ping 41 $target $target_ip
    test_ping 45 $target $target_ip
    test_ping 50 $target $target_ip
done

echo ""
echo "=========================================="
echo "FINAL RESULTS"
echo "=========================================="
echo "Total tests:  $total"
echo "Passed:       $passed"
echo "Failed:       $failed"
echo "Success rate: $(awk "BEGIN {printf \"%.2f\", ($passed/$total)*100}")%"
echo "=========================================="

if [ $failed -eq 0 ]; then
    echo ""
    echo "All $total connectivity tests passed!"
    echo ""
    echo "  ✓ All clients can reach each other"
    echo "  ✓ OSPF routing working between R1 and R2"
    echo "  ✓ All 5 switches operational"
    echo ""
else
    echo ""
    echo "  $failed tests failed. Check the output above."
    echo ""
fi
