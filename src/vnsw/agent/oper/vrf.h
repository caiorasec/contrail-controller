/*
 * Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
 */

#ifndef vnsw_agent_vrf_hpp
#define vnsw_agent_vrf_hpp

#include <boost/scoped_ptr.hpp>
#include <db/db_table_walker.h>
#include <sandesh/sandesh_types.h>
#include <sandesh/sandesh.h>
#include <cmn/agent_cmn.h>
#include <oper/route_types.h>
#include <cmn/index_vector.h>
#include <ksync/ksync_index.h>
#include <oper/peer.h>
//#include <oper/vxlan.h>
#include <oper/agent_types.h>

using namespace std;
class LifetimeActor;
class LifetimeManager;
class ComponentNHData;

struct VrfKey : public AgentKey {
    VrfKey(const string &name) : AgentKey(), name_(name) { };
    virtual ~VrfKey() { };

    void Init(const string &vrf_name) {name_ = vrf_name;};
    bool Compare(const VrfKey &rhs) const {
        return name_ == rhs.name_;
    }

    string name_;
};

struct VrfData : public AgentData {
    VrfData() : AgentData() { };
    virtual ~VrfData() { }
};

class VrfEntry : AgentRefCount<VrfEntry>, public AgentDBEntry {
public:
    class VrfNHMap;
    static const uint32_t kInvalidIndex = 0xFFFFFFFF;
    static const uint32_t kDeleteTimeout = 300 * 1000;
    VrfEntry(const string &name);
    virtual ~VrfEntry();

    virtual bool IsLess(const DBEntry &rhs) const;
    virtual KeyPtr GetDBRequestKey() const;
    virtual void SetKey(const DBRequestKey *key);
    virtual string ToString() const;

    const uint32_t GetVrfId() const {return id_;};
    const string &GetName() const {return name_;};

    uint32_t GetRefCount() const {
        return AgentRefCount<VrfEntry>::GetRefCount();
    }

    bool DBEntrySandesh(Sandesh *sresp, std::string &name) const;
    AgentRouteTable *GetRouteTable(uint8_t table_type) const; 
    Inet4UnicastRouteEntry *GetUcRoute(const Ip4Address &addr) const;
    static bool DelPeerRoutes(DBTablePartBase *part, DBEntryBase *entry,
                              Peer *peer);

    static bool VrfNotifyEntryWalk(DBTablePartBase *part, 
                                   DBEntryBase *entry, 
                                   Peer *peer);
    static bool VrfNotifyEntryMulticastWalk(DBTablePartBase *part, 
                                            DBEntryBase *entry, 
                                            Peer *peer, bool associate);

    LifetimeActor *deleter();
    void SendObjectLog(AgentLogEvent::type event) const;
    void StartDeleteTimer();
    bool DeleteTimeout();
    void CancelDeleteTimer();
    void Init();
    VrfNHMap* GetNHMap() {
        return nh_map_.get();
    }
    void AddNH(Ip4Address ip, uint8_t plen, ComponentNHData *nh_data) ;
    void DeleteNH(Ip4Address ip, uint8_t plen, ComponentNHData *nh_data) ;
    uint32_t GetNHCount(Ip4Address ip, uint8_t plen) ;
    void UpdateLabel(Ip4Address ip, uint8_t plen, uint32_t label);
    uint32_t GetLabel(Ip4Address ip, uint8_t plen);
    std::vector<ComponentNHData>* GetNHList(Ip4Address ip, uint8_t plen);
    bool FindNH(const Ip4Address &ip, uint8_t plen,
                const ComponentNHData &nh_data);

private:
    friend class VrfTable;
    class DeleteActor;
    static void DelPeerDone(DBTableBase *base, DBState *state, 
                            uint8_t table_type, const string &name,
                            Peer *peer);
    string name_;
    uint32_t id_;
    DBTableWalker::WalkId walkid_;
    boost::scoped_ptr<DeleteActor> deleter_;
    boost::scoped_ptr<VrfNHMap> nh_map_;
    AgentRouteTable *rt_table_db_[AgentRouteTableAPIS::MAX];
    Timer *delete_timeout_timer_;
    DISALLOW_COPY_AND_ASSIGN(VrfEntry);
};

class VrfTable : public AgentDBTable {
public:
    // Map from VRF Name to VRF Entry
    typedef map<string, VrfEntry *> VrfNameTree;
    typedef pair<string, VrfEntry *> VrfNamePair;

    // Map from VRF Name to Route Table
    typedef map<string, RouteTable *> VrfDbTree;
    typedef pair<string, RouteTable *> VrfDbPair;

    VrfTable(DB *db, const std::string &name) :
        AgentDBTable(db, name), db_(db),
        walkid_(DBTableWalker::kInvalidWalkerId) { };
    virtual ~VrfTable() { };

    virtual std::auto_ptr<DBEntry> AllocEntry(const DBRequestKey *k) const;
    virtual size_t Hash(const DBEntry *entry) const {return 0;};
    virtual size_t Hash(const DBRequestKey *key) const {return 0;};
    virtual void Input(DBTablePartition *root, DBClient *client,
                       DBRequest *req);
    void VrfReuse(std::string name);
    virtual DBEntry *Add(const DBRequest *req);
    virtual bool OnChange(DBEntry *entry, const DBRequest *req);
    virtual void Delete(DBEntry *entry, const DBRequest *req);
    virtual void OnZeroRefcount(AgentDBEntry *e);

    // Create a VRF entry with given name
    void CreateVrf(const string &name);
    void DeleteVrf(const string &name);
    // Create VRF Table with given name
    static DBTableBase *CreateTable(DB *db, const std::string &name);
    static VrfTable *GetInstance() {return vrf_table_;};

    virtual bool IFNodeToReq(IFMapNode *node, DBRequest &req);

    VrfEntry *FindVrfFromName(const string &name);
    VrfEntry *FindVrfFromId(size_t index) {return index_table_.At(index);};
    AgentRouteTable *GetRouteTable(const string &vrf_name, 
                                   uint8_t table_type);
    void FreeVrfId(size_t index) {index_table_.Remove(index);};

    void DelPeerRoutes(Peer *peer, Peer::DelPeerDone cb);
    void VrfTableWalkerNotify(Peer *peer);
    void VrfTableWalkerMulticastNotify(Peer *peer, bool associate);
    virtual bool CanNotify(IFMapNode *dbe);
    
private:
    void DelPeerDone(DBTableBase *base, Peer *,Peer::DelPeerDone cb);
    void VrfNotifyDone(DBTableBase *base, Peer *);
    void VrfNotifyMulticastDone(DBTableBase *base, Peer *);
    DB *db_;
    static VrfTable *vrf_table_;
    IndexVector<VrfEntry> index_table_;
    VrfNameTree name_tree_;
    VrfDbTree dbtree_[AgentRouteTableAPIS::MAX];
    DBTableWalker::WalkId walkid_;
    DISALLOW_COPY_AND_ASSIGN(VrfTable);
};

#endif // vnsw_agent_vrf_hpp
