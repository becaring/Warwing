#include "ship/events/EventSystem.h"
#include "libultraship/log/luslog.h"
#include <spdlog/spdlog.h>
#include <spdlog/sinks/base_sink.h>
#include <cassert>
#include <cstdio>
#include <string>
struct Capture : spdlog::sinks::base_sink<spdlog::details::null_mutex> {
    std::vector<std::string> lines;
    void sink_it_(const spdlog::details::log_msg& message){
        spdlog::memory_buf_t buffer;formatter_->format(message,buffer);
        lines.push_back(std::string(buffer.data(),buffer.size()));
    }
    void flush_(){}
};
static std::vector<int> order;
static void low(IEvent*){order.push_back(1);}
static void high(IEvent* event){order.push_back(2);event->Cancelled=true;}
int main(){
    Ship::EventSystem events;EventID id=events.RegisterEvent("test");assert(id==0);
    assert(events.GetEventRegistration(91)==nullptr);
    events.RegisterListener(id,high,EVENT_PRIORITY_HIGH,"high",2);
    events.RegisterListener(id,low,EVENT_PRIORITY_LOW,"low",1);
    bool duplicate=false;try{events.RegisterListener(id,low);}catch(const std::runtime_error&){duplicate=true;}assert(duplicate);
    const char key[]="key";IEvent event={false};events.CallEvent(id,&event,"caller",12,key);
    assert(order.size()==2&&order[0]==1&&order[1]==2&&event.Cancelled);
    assert(events.GetEventRegistration(id)->Callers[key].Count==1);
    events.UnregisterListener(id,0);order.clear();events.CallEvent(id,&event,"caller",12,key);
    assert(order.size()==1&&order[0]==2&&events.GetEventRegistration(id)->Callers[key].Count==2);
    std::shared_ptr<Capture> capture(new Capture);std::shared_ptr<spdlog::logger> logger(new spdlog::logger("bridge",capture));
    logger->set_pattern("[%s:%#] %v");spdlog::set_default_logger(logger);
    luslog("bridge.cpp",17,2,"literal {braces} and 100% unchanged");
    assert(capture->lines.back()=="[bridge.cpp:17] literal {braces} and 100% unchanged\n");
    lusprintf("print.cpp",9,2,"value=%d text=%s",42,"{literal}");
    assert(capture->lines.back()=="[print.cpp:9] value=42 text={literal}\n");
    std::string longText(5000,'x');lusprintf("long.cpp",3,2,"%s",longText.c_str());
    assert(capture->lines.back()=="[long.cpp:3] "+std::string(4095,'x')+"\n");
    spdlog::shutdown();
    puts("PASS actual EventSystem priority/duplicate/unregister/caller metadata and actual C logging source/literal braces/printf truncation");
}
