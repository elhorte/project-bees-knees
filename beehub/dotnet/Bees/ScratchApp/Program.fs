// open System.Text.RegularExpressions
//
// [<StructuredFormatDisplay("name=Always Harry address={address}")>]
// type Employee =
//     {
//         name : string
//         address : string
//     }
//
// type AddressContainer = 
//     {
//         employee: Employee
//         containerName: string
//     }
//
// let address1 = { name="Bob"; address="Random City" } 
// let addressContainer1 = { employee=address1; containerName= "container1"}
// printf "%s" (address1.ToString()) // prints "name=Always Harry address=Random City"
// printf "%s" (addressContainer1.ToString()) // prints {employee = name=Always Harry address=Random City;  containerName = "container1";}


open System

type t(name : string, age : int) = class
  member val name = name
  member val age = age
end

type t_ToString(name : string, age : int) = class
  inherit t(name, age)
  override __.ToString() = sprintf "t_ToString(\"%s\", %d)" name age
end

[<StructuredFormatDisplay("t_SFD (with name=\"{name}\")")>]
type t_SFD(name : string, age : int) = class
  inherit t(name, age)
  override __.ToString() = sprintf "t_SFD(\"%s\", %d)" name age
end

let pr x = printfn "ToString:\n%O\n\n%%A:\n%A\n=====" x x

let t = t("t", 7777)
(* val t : t *)
let tts = t_ToString("tts", 8888)
(* val tts : t_ToString = t_ToString("tts", 8888) *)
let tsfd = t_SFD("tsfd", 9999)
(* val tsfd : t_SFD = t_SFD (with name="tsfd") *)

#if !INTERACTIVE
[<EntryPoint>]
let main _ =
#else
let _ =
#endif
  pr t;
  pr tts;
  pr tsfd;
  0

(*
ToString:
FSI_0002+t

%A:
FSI_0002+t
=====
ToString:
t_ToString("tts", 8888)

%A:
t_ToString("tts", 8888)
=====
ToString:
t_SFD("tsfd", 9999)

%A:
t_SFD (with name="tsfd")
=====
 *)