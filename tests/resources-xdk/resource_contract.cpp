#include "ship/resource/ResourceManager.h"
#include "ship/resource/type/Json.h"
#include "ship/resource/type/Shader.h"
#include "ship/resource/ResourceFactoryBinary.h"
#include "ship/resource/archive/FolderArchive.h"
#include "ship/resource/archive/O2rArchive.h"
#include <windows.h>
#include <thread>
#include <fstream>
#include <iostream>
#include <algorithm>
#include <stdexcept>
void InstallManagerFixture(std::shared_ptr<Ship::ResourceManager>);
static void check(bool condition, const char* label) { if (!condition) throw std::runtime_error(label); }
#define CHECK(x) check(!!(x), #x)
struct ReentrantResource : Ship::Resource<void> {
    Ship::ResourceManager* manager;
    volatile LONG* destroyed;
    ReentrantResource(std::shared_ptr<Ship::ResourceInitData> data,Ship::ResourceManager* owner,volatile LONG* count)
        : Resource(data),manager(owner),destroyed(count) {}
    ~ReentrantResource(){manager->GetCachedResource(std::string("destructor-miss"));InterlockedIncrement(destroyed);}
    void* GetPointer() override{return NULL;}
    size_t GetPointerSize() override{return 0;}
};
struct ProbeFactory : Ship::ResourceFactoryBinary {
    DWORD caller;
    DWORD worker;
    HANDLE entered,release;
    Ship::ResourceManager* reentrantManager;
    volatile LONG destroyed;
    ProbeFactory(bool block=false) : caller(GetCurrentThreadId()), worker(0), entered(NULL),release(NULL),reentrantManager(NULL),destroyed(0) {
        if(block){entered=CreateEventA(NULL,TRUE,FALSE,NULL);release=CreateEventA(NULL,TRUE,FALSE,NULL);CHECK(entered && release);}
    }
    ~ProbeFactory(){if(entered)CloseHandle(entered);if(release)CloseHandle(release);}
    std::shared_ptr<Ship::IResource> ReadResource(std::shared_ptr<Ship::File> file, std::shared_ptr<Ship::ResourceInitData> data) override {
        CHECK(FileHasValidFormatAndReader(file,data));
        worker=GetCurrentThreadId();
        if(entered){CHECK(SetEvent(entered));CHECK(WaitForSingleObject(release,5000)==WAIT_OBJECT_0);}
        if(reentrantManager)return std::shared_ptr<Ship::IResource>(new ReentrantResource(data,reentrantManager,&destroyed));
        std::shared_ptr<Ship::Shader> result(new Ship::Shader(data));
        result->Data="factory-ran"; return result;
    }
};
int main(int argc,char** argv) {
    try {
        CHECK(argc==3 || argc==4);
        const std::string mode=argc==4 ? argv[3] : "normal";
        std::shared_ptr<Ship::ResourceManager> manager(new Ship::ResourceManager());
        InstallManagerFixture(manager);
        std::vector<std::string> paths;
#ifdef RESOURCE_ADAPTED
        if(mode!="single")paths.push_back(std::string(argv[1])+"/folder");
#endif
        paths.push_back(std::string(argv[1])+"/archive.o2r");
        // Two real workers also exercise the manager's nested LoadResources task.
        int reserved=static_cast<int>(std::thread::hardware_concurrency())-3;
        if(mode=="single")++reserved;
        manager->Init(paths,std::unordered_set<uint32_t>(),reserved);
        CHECK(manager->IsLoaded());
        if(mode=="single") {
            std::cout << "ENTER single-worker nested load" << std::endl;
            auto values=manager->LoadResources("assets/*");
            CHECK(values->size()==1 && values->at(0));
            InstallManagerFixture(std::shared_ptr<Ship::ResourceManager>());manager.reset();
            std::cout << "PASS single-worker queued batch" << std::endl;return 0;
        }
#ifndef RESOURCE_ADAPTED
        // Original Windows discovery has a separator bug. Feed a generic path
        // directly to its real FolderArchive to compare the remaining contract.
        std::string generic=std::string(argv[1])+"/folder";
        std::replace(generic.begin(),generic.end(),'\\','/');
        auto folder=std::make_shared<Ship::FolderArchive>(generic);folder->Load();
        CHECK(manager->GetArchiveManager()->AddArchive(folder));
#endif
        auto archives=manager->GetArchiveManager()->GetArchives();
        CHECK(archives->size()==2);
        std::shared_ptr<Ship::Archive> folderArchive,zipArchive;
        for(const auto& entry:*archives) {
            if(entry->GetManifest().Name=="Folder fixture")folderArchive=entry;
            if(entry->GetManifest().Name=="Zip fixture")zipArchive=entry;
        }
        CHECK(folderArchive && zipArchive);
        CHECK(folderArchive->GetManifest().Binaries.at("xbox")=="plugin.bin");
        CHECK(folderArchive->GetManifest().Dependencies.size()==2);
        if(mode=="teardown") {
            auto factory=std::make_shared<ProbeFactory>(true);
            CHECK(manager->GetResourceLoader()->RegisterResourceFactory(factory,RESOURCE_FORMAT_BINARY,"Probe",0x50524f42,0));
            auto pending=manager->LoadResourceAsync("probe/data");
            CHECK(WaitForSingleObject(factory->entered,5000)==WAIT_OBJECT_0);
            InstallManagerFixture(std::shared_ptr<Ship::ResourceManager>());
            HANDLE begin=CreateEventA(NULL,TRUE,FALSE,NULL),done=CreateEventA(NULL,TRUE,FALSE,NULL);
            std::thread destroyer([owner=std::move(manager),begin,done]() mutable {SetEvent(begin);owner.reset();SetEvent(done);});
            CHECK(WaitForSingleObject(begin,5000)==WAIT_OBJECT_0);
            CHECK(WaitForSingleObject(done,50)==WAIT_TIMEOUT);
            CHECK(SetEvent(factory->release));
            CHECK(pending.get());
            CHECK(WaitForSingleObject(done,5000)==WAIT_OBJECT_0);destroyer.join();CloseHandle(begin);CloseHandle(done);
            std::cout << "PASS manager teardown drains blocked real worker before member destruction" << std::endl;return 0;
        }
        auto aFuture=manager->LoadResourceAsync("assets/folder.json");
        auto a=std::dynamic_pointer_cast<Ship::Json>(aFuture.get());
        CHECK(a && a->Data["value"].get<int>()==7);
        CHECK(manager->LoadResource("assets/folder.json")==a);
        auto b=std::dynamic_pointer_cast<Ship::Json>(manager->LoadResource("assets/zip.json"));
        CHECK(b && b->Data["value"].get<int>()==9);
        CHECK(manager->LoadResource("__OTR__assets/zip.json")==b);
        CHECK(manager->LoadResource("missing")==nullptr);
        bool failed=false;
        try { manager->LoadResourceAsync("bad/data.json").get(); }
        catch(const nlohmann::json::parse_error&) { failed=true; }
        CHECK(failed);
        auto factory=std::make_shared<ProbeFactory>();
        CHECK(manager->GetResourceLoader()->RegisterResourceFactory(factory,RESOURCE_FORMAT_BINARY,"Probe",0x50524f42,0));
        auto probe=manager->LoadResourceAsync("probe/data").get();
        CHECK(probe && factory->worker && factory->worker!=factory->caller);
        auto all=manager->LoadResources("assets/*");
        CHECK(all->size()==2);
        CHECK(manager->GetArchiveManager()->ListFiles("assets/*")->size()==2);
        CHECK(manager->GetArchiveManager()->ListDirectories("assets")->size()==1);
        std::string replacement="{\"value\":11}";
        std::vector<uint8_t> bytes(64,0);
        for(unsigned i=0;i<4;++i)bytes[4+i]=static_cast<uint8_t>(0x4a534f4eU>>(8*i));
        bytes.insert(bytes.end(),replacement.begin(),replacement.end());bytes.push_back(0);
        CHECK(manager->WriteResource(Ship::ResourceIdentifier("assets/zip.json",0,std::shared_ptr<Ship::Archive>()),bytes,true));
        auto changed=std::dynamic_pointer_cast<Ship::Json>(manager->LoadResource("assets/zip.json"));
        CHECK(changed && changed->Data["value"].get<int>()==11 && b->Data["value"].get<int>()==9);
#ifdef RESOURCE_ADAPTED
        typedef decltype(manager->LoadResourceAsync("missing")) Future;
        std::vector<Future> missing;
        for(int i=0;i<500;++i)missing.push_back(manager->LoadResourceAsync("missing-"+std::to_string(i)));
        for(const auto& value:missing)CHECK(value.get()==nullptr);
        CHECK(manager->UnloadResource("assets/folder.json")==1);
        CHECK(manager->UnloadResource("assets/folder.json")==0);
        CHECK(manager->UnloadResource("probe/data")==1);probe.reset();
        factory->reentrantManager=manager.get();
        {auto owned=manager->LoadResource("probe/data");CHECK(owned);}
        CHECK(manager->UnloadResource("probe/data")==1);
        CHECK(factory->destroyed==1); // Callback reacquires cache mutex after erase unlocks.
        { Ship::O2rArchive unopened(std::string(argv[1])+"/unused.o2r"); }
        { Ship::O2rArchive corrupt(std::string(argv[1])+"/corrupt.o2r");CHECK(corrupt.Open());CHECK(!corrupt.LoadFile("data")); }
        {
            const std::string target=std::string(argv[1])+"/failure.o2r";
            Ship::O2rArchive failure(target);CHECK(failure.Open());
            HANDLE preventReplace=CreateFileA(target.c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
            CHECK(preventReplace!=INVALID_HANDLE_VALUE);
            CHECK(!failure.WriteFile("data",bytes));CHECK(CloseHandle(preventReplace));
            CHECK(!failure.Close()); // Failed write discarded and nulled its handle.
        }
#endif
        std::ofstream out(argv[2],std::ios::binary);
        out << a->Data.dump() << '\n' << changed->Data.dump() << '\n'; out.close();
        // All requested tasks have completed before destruction. The upstream
        // active-worker destructor order is a separate documented defect.
        InstallManagerFixture(std::shared_ptr<Ship::ResourceManager>());
        manager.reset();
        std::cout << "PASS actual ResourceManager queue/cache, Folder/O2r archive IO, manifest, legacy header, factory, exceptions and ZIP write/reopen\n";
        return 0;
    } catch(const std::exception& error) { std::cerr << "FAIL " << error.what() << '\n'; return 1; }
}
