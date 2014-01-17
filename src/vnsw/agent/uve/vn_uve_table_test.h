/*
 * Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
 */

#ifndef vnsw_agent_vn_uve_table_test_h
#define vnsw_agent_vn_uve_table_test_h

#include <uve/vn_uve_table.h>

class VnUveTableTest : public VnUveTable {
public:    
    VnUveTableTest(Agent *agent);
    virtual void DispatchVnMsg(const UveVirtualNetworkAgent &uve);
    uint32_t send_count() const { return send_count_; }
    uint32_t delete_count() const { return delete_count_; }

    void ClearCount();
    const VnUveEntry::VnStatsSet* FindInterVnStats(const std::string &vn);
    const VnUveEntry* GetVnUveEntry(const std::string &vn);
    int GetVnUveInterfaceCount(const std::string &vn);
    int GetVnUveVmCount(const std::string &vn);
    L4PortBitmap* GetVnUvePortBitmap(const std::string &vn);
    UveVirtualNetworkAgent* VnUveObject(const std::string &vn);
    static VnUveTableTest *GetInstance() {return singleton_;}

private:
    virtual VnUveEntryPtr Allocate(const VnEntry *vn);
    virtual VnUveEntryPtr Allocate();

    uint32_t send_count_;
    uint32_t delete_count_;
    static VnUveTableTest * singleton_;
    DISALLOW_COPY_AND_ASSIGN(VnUveTableTest);
};

#endif // vnsw_agent_vn_uve_table_test_h