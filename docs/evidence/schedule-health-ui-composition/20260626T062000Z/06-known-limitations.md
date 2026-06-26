# Known Limitations

- Cost/schedule correlation remains deferred.
- CPM recalculation is not implemented unless backend health-data reports otherwise.
- Old imports may show limited health data.
- Arbitrary compare-against behavior depends on available backend diff facts/endpoints.
- Schedule Health UI consumes backend evidence; it does not recompute parser, baseline, or diff facts.
- Screenshot capture is blocked in this environment because browser request interception is unavailable and direct Node mock API launch was rejected by command policy.
